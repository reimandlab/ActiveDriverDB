#!/usr/bin/env python3
import argparse
from database import bdb
from database import bdb_refseq
import import_data
from database import db
from models import Page
from models import User
from import_mutations import muts_import_manager
from import_mutations import get_proteins
from getpass import getpass
from helpers.commands import argument
from helpers.commands import argument_parameters
from helpers.commands import CommandTarget
from helpers.commands import command
from helpers.commands import create_command_subparsers
from app import create_app


database_binds = ('bio', 'cms')


def reset_relational_db(**kwargs):

    name = kwargs.get('bind', 'default')

    print('Removing', name, 'database...')
    db.session.commit()
    db.reflect()
    db.session.commit()
    db.drop_all(**kwargs)
    print('Removing', name, 'database completed.')

    print('Recreating', name, 'database...')
    db.create_all(**kwargs)
    print('Recreating', name, 'database completed.')


def automigrate(args):
    for database_bind in args.databases:
        basic_auto_migrate_relational_db(bind=database_bind)
    return True


def basic_auto_migrate_relational_db(**kwargs):

    name = kwargs.get('bind', 'default')

    print('Performing very simple automigration in', name, 'database...')
    db.session.commit()
    db.reflect()
    db.session.commit()
    db.create_all(**kwargs)
    print('Automigration of', name, 'database completed.')


class CMS(CommandTarget):

    description = 'should Content Managment System database be {command}ed'

    @command
    def load(args):
        content = """
        <ul>
            <li><a href="/search/proteins">search for a protein</a>
            <li><a href="/search/mutations">search for mutations</a>
        </ul>
        """
        main_page = Page(
            content=content,
            title='Visualisation Framework for Genome Mutations',
            address='index'
        )
        db.session.add(main_page)
        print('Index page created')
        print('Creating root user account')
        email = input('Please type root email: ')
        password = getpass('Please type root password: ')
        root = User(email, password)
        db.session.add(root)
        db.session.commit()
        print('Root user with email', email, 'created')

        print('Root user account created')

    @command
    def remove(args):
        reset_relational_db(bind='cms')


class ProteinRelated(CommandTarget):

    description = (
        'should chosen by the User part of biological database'
        'be {command}ed'
    )

    @command
    def load_all(args):
        import_data.import_all()

    @command
    def load(args):
        data_importers = import_data.IMPORTERS
        for importer_name in args.importers:
            importer = data_importers[importer_name]
            print('Running {name}:'.format(name=importer_name))
            results = importer()
            db.session.add_all(results)
            db.session.commit()

    @command
    def remove(args):
        reset_relational_db(bind='bio')

    @argument
    def importers():
        data_importers = import_data.IMPORTERS
        return argument_parameters(
            '-i',
            '--importers',
            nargs='*',
            help=(
                'Which importers should be used?'
                ' Available importers are: ' + ', '.join(data_importers) + '.'
                ' By default all data importers will be used.'
            ),
            choices=data_importers,
            metavar='',
            default=data_importers,
        )


class SnvToCsvMapping(CommandTarget):

    description = 'should mappings (DNA -> protein) be {command}ed'

    @command
    def load(args):
        print('Importing mappings')
        proteins = get_proteins()
        import_data.import_mappings(proteins)

    @command
    def remove(args):
        print('Removing mappigns database...')
        bdb.reset()
        bdb_refseq.reset()
        print('Removing mapings database completed.')


class Mutations(CommandTarget):

    description = 'should only mutations be {command}ed without db restart'

    @staticmethod
    def action(name, args):
        proteins = get_proteins()
        muts_import_manager.perform(
            name, proteins, args.sources
        )

    @command
    def load(args):
        Mutations.action('load', args)

    @command
    def remove(args):
        Mutations.action('delete_all', args)

    @command
    def export(args):
        Mutations.action('export', args)

    @command
    def update(args):
        Mutations.action('update', args)

    @argument
    def sources():
        mutation_importers = muts_import_manager.names

        return argument_parameters(
            '-s',
            '--sources',
            nargs='*',
            help=(
                'Which mutations should be loaded or removed?'
                ' Available sources are: ' +
                ', '.join(mutation_importers) + '.'
                ' By default all mutations will be used.'
            ),
            choices=mutation_importers,
            metavar='',
            default=mutation_importers
        )


class All(CommandTarget):

    description = 'should everything be {command}ed'

    @command
    def load(args):
        ProteinRelated.load_all(args)
        Mutations.load(argparse.Namespace(sources='__all__'))
        SnvToCsvMapping.load(args)
        CMS.load(args)


if __name__ == '__main__':
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

    # MIGRATE SUBCOMMAND
    migrate_parser = subparsers.add_parser(
        'migrate',
        help=(
            'should a basic auto migration on relational databases'
            'be performed? It will only create new tables'
        )
    )
    migrate_parser.set_defaults(func=automigrate)

    migrate_parser.add_argument(
        '-d',
        '--databases',
        type=str,
        choices=database_binds,
        default=database_binds,
        help=(
            'which databases should be automigrated?'
            ' Possible values: ' + ', '.join(database_binds) + ' '
            'By default all binds will be used.'
        )
    )

    args = parser.parse_args()

    if hasattr(args, 'func'):
        app = create_app()
        with app.app_context():
            args.func(args)
        print('Done, all tasks completed.')
    else:
        print('Scripts loaded successfuly, no tasks specified.')

else:
    print('This script should be run from command line')
