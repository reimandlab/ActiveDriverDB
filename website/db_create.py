#!/usr/bin/env python3
import argparse
from database import db
from database import bdb
from database import bdb_refseq
import import_data


def reset_relational_db(**kwargs):

    name = kwargs.get('bind', 'default')

    print('Removing', name, 'database...')
    db.reflect()    # TODO: does reflect needs bind?
    db.drop_all(**kwargs)
    print('Removing', name, 'database completed.')

    print('Recreating', name, 'database...')
    db.create_all(**kwargs)
    print('Recreating', name, 'database completed.')


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
        '-r',
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
        '-m',
        '--only_mutations',
        action='store_true',
        help='should mutations be loaded without db restart?'
    )

    args = parser.parse_args()

    if args.only_mutations:
        print('Importing mutations')
        with import_data.app.app_context():
            proteins = import_data.get_proteins()
            mutations = import_data.load_mutations(proteins, set())
    else:
        if args.reload_biological:
            reset_relational_db(bind='bio')
            print('Importing data')
            import_data.import_data()

        if args.import_mappings:
            reset_mappings_db()
            print('Importing mappings')
            with import_data.app.app_context():
                proteins = import_data.get_proteins()
                import_data.import_mappings(proteins)

        if args.recreate_cms:
            reset_relational_db(bind='cms')
            print('Creating root user account')
            # TODO

            print('Root user account created')
    print('Done, all tasks completed.')

else:
    print('This script should be run from command line')
