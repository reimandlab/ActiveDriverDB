from abc import ABCMeta, abstractmethod

from sqlalchemy.util import classproperty

from helpers.patterns import registry_metaclass_factory

AbstractRegistry = registry_metaclass_factory(ABCMeta)


class ImporterError(Exception):
    pass


class Importer(metaclass=AbstractRegistry):

    # TODO: what about fields like "parsed_count" and "results"?

    @classproperty
    def name(self):
        return self.__name__

    @abstractmethod
    def load(self):
        """Should return a list of objects to be added to database"""
        return

    @property
    def requires(self) -> list:
        """List of other importers that should be executed prior to this importer"""
        return []

    loaded = False


def importer(func):

    class FunctionImporter(Importer):

        def load(self, *args, **kwargs):
            return func(*args, **kwargs)

    FunctionImporter.__name__ = func.__name__

    return FunctionImporter().load


# TODO: idea for future: class ModelImporter(Importer):
