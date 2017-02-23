from .protein_data import IMPORTERS
from .protein_data import get_proteins
from .mutations import MutationImportManager
from database import db
# from flask import current_app


def import_all():
    print('Preparing to whole database import...')

    muts_import_manager = MutationImportManager()

    for importer_name, importer in IMPORTERS:
        print('Running %s...' % importer_name)
        results = importer()
        print('Adding %s to the session...' % importer_name)
        db.session.add_all(results)
        print('Committing changes...')
        db.session.commit()
        print('Success: %s done!')

    print('Preparing to whole database import')

    proteins = get_proteins()

    print('Importing mutations...')
    muts_import_manager.perform('load', proteins)

    db.session.commit()
    print('Done! Full database import complete!')
