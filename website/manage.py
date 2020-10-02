#!/usr/bin/env python3
import argparse
from typing import Mapping

from flask import current_app
from sqlalchemy import MetaData
from sqlalchemy.exc import OperationalError

from app import create_app
from database import bdb, get_engine
from database import bdb_refseq
from database import db
from database.manage import remove_model, reset_relational_db
from database.migrate import basic_auto_migrate_relational_db
from exports.protein_data import EXPORTERS
from helpers.commands import CommandTarget
from helpers.commands import argument
from helpers.commands import argument_parameters
from helpers.commands import command
from helpers.commands import create_command_subparsers
from imports import import_all, ImportManager
from imports.importer import BioImporter, CMSImporter
from imports.mappings import import_aminoacid_mutation_refseq_mappings
from imports.mappings import import_genome_proteome_mappings
from imports.mutations import MutationImportManager, MutationImporter
from imports.mutations import get_proteins
from models import Model

muts_import_manager = MutationImportManager()
database_binds = ('bio', 'cms')
# loading views can hinder migration as it would load models which might not be compatible with the current version
CONFIG = {'LOAD_STATS': False, 'SCHEDULER_ENABLED': False, 'USE_CELERY': False, 'LOAD_VIEWS': False}


def calc_statistics(args, app=None, stores=None):
    if not app:
        app = create_app(config_override=CONFIG)
    with app.app_context():
        if not stores:
            from stats import store_classes
            stores = store_classes
        for store_class in stores:
            store = store_class()
            store.calc_all()
        db.session.commit()


def automigrate(args, app=None):
    if not app:
        app = create_app(config_override=CONFIG)
    for database_bind in args.databases:
        basic_auto_migrate_relational_db(app, bind=database_bind)
    return True


def get_all_models(module_name='bio') -> Mapping:
    from sqlalchemy.ext.declarative.clsregistry import _ModuleMarker
    module_name = 'models.' + module_name

    models = {
        model.__name__: model
        for model in Model._decl_class_registry.values()
        if not isinstance(model, _ModuleMarker) and model.__module__.startswith(module_name)
    }
    return models


class ImportersMixin:

    @staticmethod
    def importers_choice(data_importers):
        return argument_parameters(
            '-i',
            '--importers',
            nargs='*',
            help=(
                'What should be imported?'
                ' Available choices are: ' +
                ', '.join(data_importers) + '.'
                ' By default all data will be imported.'
                ' The order of imports matters; preferable order'
                ' is the same as order of choices listed above.'
            ),
            choices=data_importers,
            metavar='',
            default=data_importers,
        )


class CMS(CommandTarget, ImportersMixin):

    import_manager = ImportManager(CMSImporter)
    description = 'should Content Management System database be {command}ed'

    @command
    def load(self, args):
        self.import_manager.import_selected(args.importers)

    @load.argument
    def importers(self):
        return self.importers_choice(self.import_manager.importers_by_name)

    @command
    def remove(self, args):
        reset_relational_db(current_app, bind='cms')


class ProteinRelated(CommandTarget, ImportersMixin):

    import_manager = ImportManager(BioImporter, ignore=MutationImporter.subclassess)
    description = (
        'should chosen by the User part of biological database'
        'be {command}ed'
    )

    @command
    def load(self, args):
        self.import_manager.import_selected(args.importers)

    @load.argument
    def importers(self):
        return self.importers_choice(self.import_manager.importers_by_name)

    @command
    def export(self, args):
        exporters = EXPORTERS
        if args.paths and len(args.paths) != len(args.exporters):
            print('Export paths should be given for every exported file, no less, no more.')
            return
        kwargs = {}
        for i, name in enumerate(args.exporters):
            exporter = exporters[name]
            if args.paths:
                kwargs['path'] = args.paths[i]
            out_file = exporter(**kwargs)
            print(f'Exported {name} to {out_file}')

    @export.argument
    def exporters(self):
        data_exporters = EXPORTERS
        return argument_parameters(
            '-e',
            '--exporters',
            nargs='*',
            help=(
                'What should be exported?'
                ' Available: ' + ', '.join(data_exporters) + '.'
                ' By default everything will be exported.'
            ),
            choices=data_exporters,
            metavar='',
            default=data_exporters,
        )

    @export.argument
    def paths(self):
        return argument_parameters(
            '--paths',
            nargs='*',
            metavar='',
            help='A path(s) for export file(s)',
        )

    @command
    def remove_all(self, args):
        reset_relational_db(current_app, bind='bio')

    @command
    def remove(self, args):
        models = get_all_models('bio')
        to_remove = args.models

        if args.all:
            to_remove = models.keys()
        elif not args.models:
            print('Please specify model(s) to remove with --model or --all')

        for model_name in to_remove:
            model = models[model_name]
            remove_model(model)
            db.session.commit()

    @remove.argument
    def all(self):
        return argument_parameters(
            '--all', '-a',
            action='store_true',
            help='Remove all bio models.'
        )

    @remove.argument
    def models(self):

        models = get_all_models('bio')

        return argument_parameters(
            '--models', '-m',
            nargs='+',
            metavar='',
            help=(
                'Names of models to be removed.'
                ' Available models: ' + ', '.join(models) + '.'
            ),
            default=[],
            choices=models.keys()
        )


class Mappings(CommandTarget):

    description = 'should mappings (DNA -> protein) be {command}ed'

    @command
    def load(self, args):
        print(f'Importing {args.restrict_to or "all"} mappings')

        if args.restrict_to != 'aminoacid_refseq':
            from sqlalchemy.orm import load_only
            proteins = get_proteins(options=load_only('id', 'refseq', 'sequence'))

            import_genome_proteome_mappings(proteins, bdb_dir=args.path)

        if args.restrict_to != 'genome_proteome':
            from models import Gene, Protein
            from database import db
            from collections import namedtuple

            protein = namedtuple('Protein', ('id', 'refseq', 'sequence', 'gene_name'))

            proteins = {
                data[1]: protein(*data)
                for data in (
                    db.session.query(Protein.id, Protein.refseq, Protein.sequence, Gene.name)
                    .select_from(Protein).join(Protein.gene)
                )
            }

            import_aminoacid_mutation_refseq_mappings(proteins, bdb_dir=args.path)

    @load.argument
    def restrict_to(self):
        return argument_parameters(
            '--restrict_to', '-r',
            default=None,
            choices=['genome_proteome', 'aminoacid_refseq'],
            help='Should only genome_proteome or aminoacid_refseq mappings be imported?'
        )

    @load.argument
    def path(self):
        return argument_parameters(
            '--path',
            type=str,
            default='',
            help='A path to dir where mappings dbs should be created'
        )

    @command
    def remove(self, args):
        print('Removing mappings database...')
        bdb.reset()
        bdb_refseq.reset()
        print('Removing mappings database completed.')


class Mutations(CommandTarget):

    description = 'should only mutations be {command}ed without db restart'

    @staticmethod
    def action(name, args):
        proteins = get_proteins()
        kwargs = vars(args)
        if 'func' in kwargs:
            kwargs.pop('func')
        if 'type' in kwargs:
            kwargs.pop('type')
        muts_import_manager.perform(
            name, proteins, **kwargs
        )

    @command
    def load(self, args):
        self.action('load', args)

    @command
    def remove(self, args):
        self.action('remove', args)

    @command
    def export(self, args):
        if args.type == 'proteomic':
            self.action('export', args)
        else:
            assert args.type == 'genomic_ptm'
            self.action('export_genomic_coordinates_of_ptm', args)

    @command
    def update(self, args):
        self.action('update', args)

    @argument
    def sources(self):
        mutation_importers = muts_import_manager.names

        return argument_parameters(
            '-s',
            '--sources',
            nargs='*',
            help=(
                'Which mutations should be loaded or removed?'
                ' Available sources are: ' +
                ', '.join(mutation_importers) + '.'
                ' By default all sources will be used.'
            ),
            choices=mutation_importers,
            metavar='',
            default=mutation_importers
        )

    @load.argument
    def chunk(self):
        return argument_parameters(
            '-c',
            '--chunk',
            type=int,
            default=None,
            help='Limit import to n-th chunk, starts with 0. By default None.'
        )

    @export.argument
    def only_primary_isoforms(self):
        return argument_parameters(
            '-o',
            '--only_primary_isoforms',
            action='store_true',
            help='Restrict export to primary isoforms',
        )

    @export.argument
    def type(self):
        return argument_parameters(
            '-t',
            '--type',
            default='proteomic',
            choices=['proteomic', 'genomic_ptm'],
            help='What type of mutations should be exported: proteomic or genomic_ptm (genomic affecting PTM).'
                 ' By default proteomic mutations will be exported',
        )


class All(CommandTarget):

    description = 'should everything be {command}ed'

    @command
    def load(self, args):
        import_all()
        Mappings().load(args)

    @command
    def remove(self, args):
        ProteinRelated().remove_all(args)
        Mutations().remove(argparse.Namespace(sources='__all__'))
        Mappings().remove(args)
        CMS().remove(args)


def new_subparser(subparsers, name, func, **kwargs):
    subparser = subparsers.add_parser(name, **kwargs)
    subparser.set_defaults(func=func)
    return subparser


def run_shell(args):
    print('Starting interactive shell...')
    app = create_app(config_override=CONFIG)
    with app.app_context():
        if args.command:
            print(f'Executing supplied command: "{args.command}"')
            exec(args.command)

        print('You can access current application using "app" variable.')
        print('Database, models and statistics modules are pre-loaded.')

        import models
        locals().update(vars(models))

        fallback = False
        if not args.raw:
            try:
                from IPython import embed
                embed()
            except ImportError:
                print('To use enhanced interactive shell install ipython3')
                fallback = True

        if fallback or args.raw:
            import code
            code.interact(local=locals())


def entity_diagram(args, app=None):
    from eralchemy import render_er
    if not app:
        app = create_app(config_override=CONFIG)
    for database_bind in args.databases:
        engine = get_engine(database_bind, app)
        meta = MetaData()
        meta.reflect(bind=engine)
        render_er(meta, f'{database_bind}_model_sqlalchemy.{args.format}')


def create_parser():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help='sub-commands')

    data_subcommands = ['load', 'remove', 'export', 'update']

    command_subparsers = {
        subcommand: subparsers.add_parser(
            subcommand,
            help='{0} data from specified category'.format(subcommand)
        )
        for subcommand in data_subcommands
    }

    create_command_subparsers(command_subparsers)

    new_subparser(
        subparsers,
        'calc_stats',
        calc_statistics,
        help=(
            'should statistics (counts of protein, pathways, mutation, etc) be recalculated?'
        )
    )

    shell_parser = new_subparser(
        subparsers,
        'shell',
        run_shell
    )

    shell_parser.add_argument(
        '-r',
        '--raw',
        action='store_true'
    )

    shell_parser.add_argument(
        '-c',
        '--command',
        type=str
    )

    er_parser = new_subparser(
        subparsers,
        'er_diagram',
        entity_diagram,
        help='plot entity-relationship diagram'
    )

    er_parser.add_argument(
        '-d',
        '--databases',
        type=str,
        nargs='*',
        choices=database_binds,
        default=database_binds,
    )

    er_parser.add_argument(
        '-f',
        '--format',
        type=str,
        default='png'
    )

    migrate_parser = new_subparser(
        subparsers,
        'migrate',
        automigrate,
        help=(
            'should a basic auto migration on relational databases'
            ' be performed? It will create new tables, columns and'
            ' suggest other updates.'
        )
    )

    migrate_parser.add_argument(
        '-d',
        '--databases',
        type=str,
        nargs='*',
        choices=database_binds,
        default=database_binds,
        help=(
            'which databases should be automigrated?'
            ' Possible values: ' + ', '.join(database_binds) + ' '
            'By default all binds will be used.'
        )
    )
    return parser


def run_manage(parsed_args, app=None):
    if not hasattr(parsed_args, 'func'):
        print('Scripts loaded successfully, no tasks specified.')
        return

    if not app:
        try:
            app = create_app(config_override=CONFIG)
        except OperationalError as e:
            if e.orig.args[0] == 1071:
                print('Please run: ')
                for bind in ['bio', 'cms']:
                    engine = db.get_engine(app, bind)
                    print(f'ALTER DATABASE `{engine.url.database}` CHARACTER SET utf8;')
                print('to be able to continue.')
                print(e)
                return
            else:
                raise

    with app.app_context():
        parsed_args.func(parsed_args)

    print('Done, all tasks completed.')


if __name__ == '__main__':
    parser = create_parser()

    arguments = parser.parse_args()
    run_manage(arguments)
