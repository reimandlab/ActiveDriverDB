from abc import ABCMeta, abstractmethod

from sqlalchemy.util import classproperty

from helpers.patterns import registry_metaclass_factory
from helpers.utilities import to_snake_case

AbstractRegistry = registry_metaclass_factory(ABCMeta)


class ImporterError(Exception):
    pass


class AbstractImporter:

    # TODO: what about fields like "parsed_count" and "results"?

    @classproperty
    def name(self):
        name = self.__name__
        if name.endswith('Importer'):
            name = name[:-8]
        return to_snake_case(name)

    @abstractmethod
    def load(self):
        """Should return a list of objects to be added to database"""
        return

    @property
    def requires(self) -> list:
        """List of other importers that should be executed prior to this importer"""
        return []

    loaded = False


class BioImporter(AbstractImporter, metaclass=AbstractRegistry):
    pass


class CMSImporter(AbstractImporter, metaclass=AbstractRegistry):
    pass


def create_simple_importer(importer_abstract_class):
    def importer(func):

        class FunctionImporter(importer_abstract_class):

            def load(self, *args, **kwargs):
                return func(*args, **kwargs)

        FunctionImporter.__name__ = func.__name__

        return FunctionImporter().load
    return importer


# TODO: idea for future: class ModelImporter(Importer):
