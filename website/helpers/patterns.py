def registry_metaclass_factory(base_type):

    class RegisterMetaClass(base_type):

        def __init__(cls, name, bases, newattrs):

            super().__init__(name, bases, newattrs)

            if not hasattr(cls, 'registry'):
                cls.registry = list()

            cls.registry.append(cls)
            for base in bases:
                if base in cls.registry:
                    cls.registry.remove(base)

        def __iter__(cls):
            return iter(cls.registry)

    return RegisterMetaClass


Register = registry_metaclass_factory(type)
