from collections import Iterable


def is_iterable_but_not_str(obj):
    return isinstance(obj, Iterable) and not isinstance(obj, str)
