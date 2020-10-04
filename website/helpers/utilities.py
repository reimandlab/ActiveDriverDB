import re
from collections.abc import Iterable


def is_iterable_but_not_str(obj):
    return isinstance(obj, Iterable) and not isinstance(obj, str)


def to_snake_case(text: str):
    return re.sub('([A-Z]+)', r'_\1', text).lower().lstrip('_')
