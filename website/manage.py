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


def automigrate(args, app=None):
    if not app:
        app = create_app()
    for database_bind in args.databases:
        basic_auto_migrate_relational_db(app, bind=database_bind)
    return True


def column_names(table):
    return set((i.name for i in table.c))


def basic_auto_migrate_relational_db(app, bind):
    """Inspired with http://stackoverflow.com/questions/2103274/"""

    from sqlalchemy import Table
    from sqlalchemy import MetaData

    print('Performing very simple automigration in', bind, 'database...')
    db.session.commit()
    db.reflect()
    db.session.commit()
    db.create_all(bind=bind)

    with app.app_context():
        engine = db.get_engine(app, bind)
        tables = db.get_tables_for_bind(bind=bind)
        metadata = MetaData()
        metadata.engine = engine

        ddl = engine.dialect.ddl_compiler(engine.dialect, None)

        for table in tables:

            db_table = Table(
                table.name, metadata, autoload=True, autoload_with=engine
            )
            db_columns = column_names(db_table)

            columns = column_names(table)
            new_columns = columns - db_columns
            unused_columns = db_columns - columns

            for column_name in new_columns:
                column = getattr(table.c, column_name)
                if column.constraints:
                    print(
                        'Column %s skipped due to existing constraints.'
                        % column_name
                    )
                    continue
                print('Creating column: %s' % column_name)

                definition = ddl.get_column_specification(column)
                sql = 'ALTER TABLE %s ADD %s' % (table.name, definition)
                engine.execute(sql)

            if unused_columns:
                print(
                    'Following columns in %s table are no longer used '
                    'and can be safely removed:' % table.name
                )
                for column in unused_columns:
                    answered = False
                    while not answered:
                        answer = input('%s: remove (y/n)? ' % column)
                        if answer == 'y':
                            sql = (
                                'ALTER TABLE %s DROP %s'
                                % (table.name, column)
                            )
                            engine.execute(sql)
                            print('Removed column %s.' % column)
                            answered = True
                        elif answer == 'n':
                            print('Keeping column %s.' % column)
                            answered = True

    print('Automigration of', bind, 'database completed.')


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
    def export(args):
        exporters = import_data.EXPORTERS
        for name in args.exporters:
            exporter = exporters[name]
            out_file = exporter()
            print('Exported %s to %s' % (name, out_file))

    @command
    def remove(args):
        reset_relational_db(bind='bio')

    @argument
    def exporters():
        data_exporters = import_data.EXPORTERS
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
        print('Removing mappings database...')
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

    @argument
    def only_primary_isoforms():
        return argument_parameters(
            '-o',
            '--only_primary_isoforms',
            action='store_true',
            help='Restrict export to primary isoforms',
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
        nargs='*',
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
