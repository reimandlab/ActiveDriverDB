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
        self.ordered_importers = self.resolve_import_order()
        self.importers_by_name = {
            importer.name: importer
            for importer in self.ordered_importers
        }

    def import_all(self):
        self.import_selected(importers_subset=self.ordered_importers)

    def import_selected(self, importers_subset: List[str] = None, dry=False):

        if not importers_subset:
            print('Importing all')
            importers_subset = [importer.name for importer in self.ordered_importers]

        for importer_name in importers_subset:
            importer = self.importers_by_name[importer_name]()
            print(f'Running {importer_name}:')
            results = importer.load()
            if results:
                print(f'Got {len(results)} results.')
                if not dry:
                    print(f'Adding {importer.name} results to the session...')
                    db.session.add_all(results)
                else:
                    print('Running in dry mode, not adding to the session')
            if not dry:
                print('Committing changes...')
                db.session.commit()
            print(f'Success: {importer.name} done!')

    def resolve_import_order(self):
        # make a copy of importers list
        unordered = self.importers[:]

        ordered = []

        past_unordered = set()

        while unordered:
            if tuple(unordered) in past_unordered:
                raise ValueError('Cycle detected', unordered)
            past_unordered.add(tuple(unordered))

            importer = unordered.pop(0)

            requirements_satisfied = True

            for requirement in importer.requires:

                if requirement not in ordered:
                    try:
                        unordered.remove(requirement)
                        print(unordered)
                    except ValueError as e:
                        raise ValueError(
                            f'It might be that the requirement {requirement.name}'
                            f' is not registered among the top-level importers ({e})'
                        )
                    unordered = [requirement, importer] + unordered
                    requirements_satisfied = False
                    break

            if requirements_satisfied:
                ordered.append(importer)

        return ordered
