from abc import ABCMeta, abstractmethod
from typing import Type, Callable

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


def simple_importer(
    importer_abstract_class: Type[AbstractImporter],
    requires=None
) -> Callable[[Callable], Type[AbstractImporter]]:
    def importer(func) -> Type[AbstractImporter]:

        class FunctionImporter(importer_abstract_class):

            @staticmethod
            def load(*args, **kwargs):
                return func(*args, **kwargs)

            def __repr__(self):
                return f'<{func.__module__}.{func.__name__} importer>'

        FunctionImporter.requires = requires or []
        FunctionImporter.__name__ = f'{func.__name__}Importer'
        FunctionImporter.__doc__ = func.__doc__

        return FunctionImporter   # type: Type[AbstractImporter]
    return importer


# TODO: idea for future: class ModelImporter(Importer):
