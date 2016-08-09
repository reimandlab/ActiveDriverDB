#!/usr/bin/env python3
from database import db
from database import bdb
from database import bdb_refseq
from import_data import import_data
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

    args = parser.parse_args()

    if args.import_mappings:
        reset_mappings_db()

    if args.reload_relational:
        restet_relational_db()

    if args.reload_relational or args.import_mappings:
        print('Importing data')
        import_data(
            import_mappings=args.import_mappings,
            reload_relational=args.reload_relational
        )
        print('Importing completed')

    print('Done, all tasks completed.')

else:
    print('This script should be run from command line')
