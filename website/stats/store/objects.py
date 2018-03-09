from copy import copy
from functools import lru_cache, partial
from itertools import product
from types import FunctionType


class StoreObject:

    def __init__(self, func: callable, static=False):
        self.func = func
        self.static = static

    def __call__(self, store_context=None):
        func = self.func
        if hasattr(func, '__self__') or self.static:
            return func()
        else:
            return func(store_context)

    @property
    def name(self):
        if hasattr(self.func, 'name'):
            return self.func.name

    def as_staticmethod(self):
        store_object = copy(self)
        store_object.static = True
        return store_object


class Counter(StoreObject):

    def __init__(self, func: FunctionType, name=None, cache=True, static=False):
        if cache:
            func = lru_cache(maxsize=1)(func)
        if name:
            func.name = name
        super().__init__(func, static)


def compose_name(name: str, value) -> str:

    if isinstance(value, list):
        return '_'.join([compose_name(name, v) for v in value])
    if isinstance(value, bool):
        return f'{name}:{value}'
    elif hasattr(value, 'name'):
        return value.name
    elif callable(value):
        return value.__name__
    elif value is None:
        return ''
    return str(value)


class CaseGenerator(StoreObject):

    def __init__(self, func: FunctionType, cases, mode):
        super().__init__(func)
        self.cases = cases
        self.mode = mode

    @staticmethod
    def full_case_name(kwargs):
        parts = []

        for case_name, case_value in kwargs.items():
            part = compose_name(case_name, case_value)
            if part == '':
                continue
            parts.append(part)
        return '_'.join(parts)

    def generate(self, case_wrapper=lambda case: case):
        transform = CasesDecorator.modes[self.mode]

        for kwargs in transform(self.cases):

            func_case = case_wrapper(partial(self.func, **kwargs))

            if hasattr(self.func, '__self__'):
                func_case.__self__ = self.func.__self__

            yield self.full_case_name(kwargs), func_case


def independent_cases(func_cases: dict):
    for key, values in func_cases.items():
        for case in values:
            yield {key: case}


def product_cases(func_cases: dict):
    for values in product(*func_cases.values()):
        yield dict(zip(func_cases.keys(), values))


class CasesDecorator:

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.mode = 'independent'

    def __call__(self, func):
        return CaseGenerator(func, cases=self.kwargs, mode=self.mode)

    def set_mode(self, new_mode):
        if new_mode not in self.modes:
            raise ValueError(f'Invalid mode: {new_mode}; accepted: {", ".join(self.modes)}')
        self.mode = new_mode
        return self

    modes = {
        'independent': independent_cases,
        'product': product_cases
    }
