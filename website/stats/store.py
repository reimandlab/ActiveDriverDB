import re
from functools import lru_cache, partial
from itertools import product
from types import FunctionType
from warnings import warn

from tqdm import tqdm

from database import get_or_create, db
from models import Count


def counter(func: FunctionType, name=None, cache=True):
    if cache:
        func = lru_cache(maxsize=1)(func)
    if name:
        func.name = name
    func.is_counter = True
    return func


def independent_cases(func_cases: dict):
    for key, values in func_cases.items():
        for case in values:
            yield {key: case}


def product_cases(func_cases: dict):
    for values in product(*func_cases.values()):
        yield dict(zip(func_cases.keys(), values))


class Cases:

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.mode = 'independent'

    def __call__(self, func):
        func.cases = self.kwargs
        func.mode = self.mode
        return func

    def set_mode(self, new_mode):
        if new_mode not in self.modes:
            raise ValueError(f'Invalid mode: {new_mode}; accepted: {", ".join(self.modes)}')
        self.mode = new_mode
        return self

    modes = {
        'independent': independent_cases,
        'product': product_cases
    }

    @classmethod
    def full_case_name(cls, kwargs):
        parts = []

        def compose_name(name: str, value) -> str:

            if isinstance(value, list):
                return '_'.join([compose_name(name, v) for v in value])
            if isinstance(value, bool):
                return f'{name}:{value}'
            elif hasattr(case_value, 'name'):
                return value.name
            elif callable(value):
                return value.__name__
            elif value in [None, '']:
                return
            return str(value)

        for case_name, case_value in kwargs.items():
            part = compose_name(case_name, case_value)
            if part is None:
                continue
            parts.append(part)
        return '_'.join(parts)

    @classmethod
    def iter_cases(cls, func_with_cases):

        if not hasattr(func_with_cases, 'cases'):
            return []

        transform = cls.modes[func_with_cases.mode]

        for kwargs in transform(func_with_cases.cases):
            func_case = counter(partial(func_with_cases, **kwargs))
            func_case.__self__ = func_with_cases.__self__

            yield cls.full_case_name(kwargs), func_case


cases = Cases


class CountStore:

    storage_model = Count

    def register(self, _counter, name=None):
        if not name:
            if hasattr(_counter, 'name'):
                name = _counter.name
            else:
                name = _counter.__name__
        if name in self.__dict__:
            warn(f'{name} was registered twice')
        self.__dict__[name] = _counter

    def __init__(self):
        for name, member in self.members.items():
            for case_name, new_counter in Cases.iter_cases(member):
                full_name = name + ('_' + case_name if case_name else '')
                self.register(new_counter, name=full_name)

    @property
    def members(self):
        return {
            name: getattr(self, name)
            for name in dir(self)
            if name not in ['members', 'counters']
        }

    @property
    def counters(self):
        return {
            value.name if hasattr(value, 'name') else name: value
            for name, value in self.members.items()
            if callable(value) and hasattr(value, 'is_counter')
        }

    def calc_all(self, limit_to=None):
        """Calculate all counts and save calculated values into database.

        Already existing values will be updated.

        Args:
            limit_to: regular expression for limiting which counters should be executed
        """

        counters = {
            _counter.name if hasattr(_counter, 'name') else name: _counter
            for name, _counter in self.counters.items()
        }

        counters = {
            name: _counter
            for name, _counter in counters.items()
            if not limit_to or re.match(limit_to, name)
        }

        for name, _counter in tqdm(counters.items(), total=len(counters)):

            count, new = get_or_create(self.storage_model, name=name)

            if hasattr(_counter, '__self__'):
                value = _counter()
            else:
                value = _counter(self)

            count.value = value

            print(name, value)

            if new:
                db.session.add(count)

    def get_all(self):

        model = self.storage_model

        counts = {
            counter_name: db.session.query(model.value).filter(model.name == counter_name).scalar() or 0
            for counter_name in self.counters.keys()
        }

        return counts
