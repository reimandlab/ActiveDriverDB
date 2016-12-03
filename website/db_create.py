#!/usr/bin/env python3
import argparse
from database import bdb
from database import bdb_refseq
import import_data
from database import db
from models import Page
from models import User
import import_mutations
from getpass import getpass


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


def basic_auto_migrate_relational_db(**kwargs):

    name = kwargs.get('bind', 'default')

    print('Performing very simple automigration in', name, 'database...')
    db.session.commit()
    db.reflect()
    db.session.commit()
    db.create_all(**kwargs)
    print('Automigration of ', name, 'database completed.')


def reset_mappings_db():
    print('Removing mappigns database...')
    bdb.reset()
    bdb_refseq.reset()
    print('Removing mapings database completed.')

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-i',
        '--import_mappings',
        action='store_true',
        help='should mappings (DNA -> protein) be (re)imported'
    )
    parser.add_argument(
        '-b',
        '--reload_biological',
        action='store_true',
        help='should biological database be (re)imported.'
    )
    parser.add_argument(
        '-c',
        '--recreate_cms',
        action='store_true',
        help='should Content Managment System database be (re)created'
    )
    parser.add_argument(
        '-a',
        '--auto_migrate',
        action='store_true',
        help=(
            'should very basic auto migration on relational databases'
            ' be performed'
        )
    )
    parser.add_argument(
        '-l',
        '--load_mutations',
        action='store_true',
        help='should mutations be loaded without db restart?'
    )
    importers = import_mutations.get_all_importers().keys()
    parser.add_argument(
        '-m',
        '--mutation_sources',
        nargs='*',
        help=(
            'Which mutations should be loaded or removed?'
            ' Available sources are: ' + ', '.join(importers) + '.'
            ' By default all mutations will be used.'
        ),
        choices=importers,
        metavar='',
        default='__all__',
    )
    parser.add_argument(
        '-r',
        '--remove_mutations',
        action='store_true',
        help='should only mutations be removed without db restart?'
    )

    args = parser.parse_args()

    if args.remove_mutations:
        with import_data.app.app_context():
            import_mutations.remove_mutations(args.mutation_sources)

    if args.load_mutations:
        with import_data.app.app_context():
            proteins = import_mutations.get_proteins()
            mutations = import_mutations.load_mutations(
                proteins,
                args.mutation_sources
            )

    if not args.load_mutations and not args.remove_mutations:

        if args.auto_migrate:
            basic_auto_migrate_relational_db(bind='bio')
            basic_auto_migrate_relational_db(bind='cms')

        if args.reload_biological:
            reset_relational_db(bind='bio')
            print('Importing data')
            import_data.import_data(args.mutation_sources)

        if args.import_mappings:
            reset_mappings_db()
            print('Importing mappings')
            with import_data.app.app_context():
                proteins = import_mutations.get_proteins()
                import_data.import_mappings(proteins)

        if args.recreate_cms:
            content = """
            <ul>
                <li><a href="/search/proteins">search for a protein</a>
                <li><a href="/search/mutations">search for mutations</a>
            </ul>
            """
            reset_relational_db(bind='cms')
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
    print('Done, all tasks completed.')

else:
    print('This script should be run from command line')
