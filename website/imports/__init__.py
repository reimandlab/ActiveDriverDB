from database import db

from .importer import Importer
from .protein_data import get_proteins
from .mutations import MutationImportManager
from . import sites


class ImportManager:

    def __init__(self):
        self.importers = Importer.registry

    def import_all(self):

        ordered_importers = self.resolve_import_order()

        for importer_class in ordered_importers:
            importer = importer_class()
            print('Running %s...' % importer.name)
            results = importer.load()
            if results:
                print('Got %s results.' % len(results))
                print('Adding %s to the session...' % importer.name)
                db.session.add_all(results)
            print('Committing changes...')
            db.session.commit()
            print('Success: %s done!' % importer.name)

    def resolve_import_order(self):
        # make a copy of importers list
        unordered = self.importers[:]

        ordered = []

        while unordered:
            importer = unordered.pop()

            requirements_satisfied = True

            for requirement in importer.requires:

                if requirement not in ordered:
                    unordered.pop(requirement)
                    unordered = [requirement, importer] + unordered
                    requirements_satisfied = False
                    break

            if requirements_satisfied:
                ordered.append(importer)

        return ordered


def import_all():
    print('Preparing to whole database import...')

    import_manager = ImportManager()

    import_manager.import_all()

    muts_import_manager = MutationImportManager()

    proteins = get_proteins()

    print('Importing mutations...')
    muts_import_manager.perform('load', proteins)

    db.session.commit()
    print('Done! Full database import complete!')
