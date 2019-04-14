from typing import Type, List

from database import db
from imports import AbstractImporter


class ImportManager:

    def __init__(self, importer_abstract_class: Type[AbstractImporter], ignore=None):
        self.importers = [
            importer
            for importer in importer_abstract_class.registry
            if not ignore or importer not in ignore
        ]
        self.importers_by_name = {
            importer.name: importer
            for importer in self.importers
        }

    def import_all(self):

        ordered_importers = self.resolve_import_order()
        importers_names = [importer.name for importer in ordered_importers]

        self.import_selected(importers_subset=importers_names)

    def import_selected(self, importers_subset: List[str]=None):

        if not importers_subset:
            importers_subset = self.importers_by_name.keys()

        for importer_name in importers_subset:
            importer = self.importers_by_name[importer_name]()
            print(f'Running {importer_name}:')
            results = importer.load()
            if results:
                print(f'Got {len(results)} results.')
                print(f'Adding {importer.name} results to the session...')
                db.session.add_all(results)
            print('Committing changes...')
            db.session.commit()
            print(f'Success: {importer.name} done!')

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
