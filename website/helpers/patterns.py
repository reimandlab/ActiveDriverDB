from abc import abstractmethod
from collections import defaultdict


def registry_metaclass_factory(base_type):

    class RegisterMetaClass(base_type):

        def __init__(cls, name, bases, newattrs):

            super().__init__(name, bases, newattrs)

            if not hasattr(cls, 'registry'):
                cls.registry = list()
                cls.hierarchy = defaultdict(set)

            cls.registry.append(cls)

            for base in bases:
                if base in cls.registry:
                    cls.registry.remove(base)
                cls.hierarchy[base].add(cls)

        def __iter__(cls):
            return iter(cls.registry)

        @property
        def subclassess(self):
            all_subclasses = self.hierarchy[self]
            to_visit = list(all_subclasses)
            for subclass in to_visit:
                grandchildren = self.hierarchy[subclass]
                all_subclasses.update(grandchildren)
                to_visit.extend(grandchildren)
            return all_subclasses

    return RegisterMetaClass


Register = registry_metaclass_factory(type)


def abstract_property(func):
    return property(abstractmethod(func))
