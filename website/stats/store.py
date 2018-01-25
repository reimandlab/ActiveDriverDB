from functools import lru_cache, partial
from types import FunctionType

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


def cases(**kwargs):
    def decorator(func):
        func.cases = kwargs
        return func
    return decorator


class CountStore:

    storage_model = Count

    def register(self, _counter, name=None):
        if not name:
            if hasattr(_counter, 'name'):
                name = _counter.name
            else:
                name = _counter.__name__
        self.__dict__[name] = _counter

    def __init__(self):
        for name, member in self.members.items():
            if hasattr(member, 'cases'):
                for key, value in member.cases.items():
                    for case in value:
                        new_counter = counter(partial(member, **{key: case}))
                        new_counter.__self__ = member.__self__
                        if isinstance(case, bool):
                            case = f'{key}:{case}'
                        self.register(new_counter, name=f'{name}_{case}')

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

    def calc_all(self):

        counters = self.counters

        for name, _counter in tqdm(counters.items(), total=len(counters)):
            if hasattr(_counter, 'name'):
                name = _counter.name

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
