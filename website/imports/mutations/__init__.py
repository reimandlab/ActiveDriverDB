from importlib import import_module
from os.path import basename
from typing import List, Mapping, Type

from helpers.parsers import get_files
from imports.protein_data import get_proteins

from .mutation_importer import MutationImporter


# rename to MutationOperationManager?
class MutationImportManager:

    ignored_files = [
        '.', '..',
        '__init__',
    ]

    def __init__(self, lookup_dir='imports/mutations'):
        self.importers = self._discover_importers(lookup_dir)

    def _discover_importers(self, lookup_dir) -> Mapping[str, Type[MutationImporter]]:
        # import relevant modules
        modules = {}
        package = lookup_dir.replace('/', '.')

        for path in get_files(lookup_dir, '*.py'):
            name = basename(path)[:-3]
            if name in self.ignored_files:
                continue
            modules[name] = import_module('.' + name, package=package)

        # make use of the registry metaclass:
        return {
            importer.name: importer
            for importer in MutationImporter.subclassess
            if not importer.__abstractmethods__
        }

    def select(self, restrict_to: List[str]):
        if not restrict_to:
            return self.importers
        return {
            name: self.importers[name]
            for name in restrict_to
        }

    def explain_action(self, action, sources):
        print('{action} mutations from: {sources} source{suffix}'.format(
            action=action,
            sources=(
                ', '.join(sources)
                if set(sources) != set(self.importers.keys())
                else 'all'
            ),
            suffix='s' if len(sources) > 1 else ''
        ))

    def perform(self, action, proteins=None, sources='__all__', paths=None, **kwargs):
        if sources == '__all__':
            sources = self.names

        self.explain_action(action, sources)

        importers = self.select(sources)
        path = None

        if not proteins:
            proteins = get_proteins()

        for name, importer_class in importers.items():
            if paths:
                path = paths[name]

            importer = importer_class(proteins)
            method = getattr(importer, action)
            method(path=path, **kwargs)

        print(f'Mutations {action}ed')

    @property
    def names(self):
        return self.importers.keys()
