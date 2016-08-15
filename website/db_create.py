#!/usr/bin/env python3
from database import db
from database import bdb
from database import bdb_refseq
import import_data
import argparse


def restet_relational_db():

    print('Removing relational database...')
    db.reflect()
    db.drop_all()
    print('Removing relational database completed.')

    print('Recreating relational database...')
    db.create_all()
    print('Recreating relational database completed.')


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
        help='Should mappings be (re)imported'
    )
    parser.add_argument(
        '-r',
        '--reload_relational',
        action='store_true',
        help='Should relational database be (re)imported'
    )
    parser.add_argument(
        '-m',
        '--only_mutations',
        action='store_true',
        help='Should mutations be loaded without db restart?'
    )

    args = parser.parse_args()

    if args.only_mutations:
        print('Importing mutations')
        with app.app_context():
            proteins = import_data.get_proteins()
            mutations = import_data.load_mutations(proteins, set())
    else:
        if args.reload_relational:
            restet_relational_db()
            print('Importing data')
            import_data.import_data()

        if args.import_mappings:
            reset_mappings_db()
            with app.app_context():
                proteins = get_proteins()
                import_data.import_mappings(proteins)

    print('Done, all tasks completed.')

else:
    print('This script should be run from command line')
