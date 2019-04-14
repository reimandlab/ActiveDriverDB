from database import db
from imports.mutations import MutationImporter

from .importer import AbstractImporter, BioImporter, CMSImporter
from .manager import ImportManager
from .protein_data import get_proteins
from .mutations import MutationImportManager
from . import sites
from . import cms


def import_all():
    print('Preparing to whole database import...')

    bio_import_manager = ImportManager(BioImporter, ignore=MutationImporter.subclassess)
    bio_import_manager.import_all()

    # mutations need protein information
    muts_import_manager = MutationImportManager()

    proteins = get_proteins()

    print('Importing mutations...')
    muts_import_manager.perform('load', proteins)

    # when creating cms user action is needed, so it should be the last step
    cms_import_manager = ImportManager(CMSImporter)
    cms_import_manager.import_all()

    db.session.commit()
    print('Done! Full database import complete!')
