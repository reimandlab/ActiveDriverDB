import re
from functools import partial
from warnings import warn

from tqdm import tqdm

from database import get_or_create, db
from models import Count

from .objects import StoreObject, Counter, CaseGenerator


class CountStore:

    storage_model = Count
    default = 0

    def register(self, stored_object, name=None):
        if not name:
            name = stored_object.name
        if name in self.__dict__:
            warn(f'{name} was registered twice')
        self.__dict__[name] = stored_object

    def __init__(self):
        for name, case_generator in self.case_generators.items():
            counter = partial(Counter, static=case_generator.static)
            for case_name, new_counter in case_generator.generate(case_wrapper=counter):
                full_name = name + ('_' + case_name if case_name else '')
                self.register(new_counter, name=full_name)

    @property
    def storables(self):
        to_skip = ['storables', 'counters', 'case_generators']
        store_objects = {}
        for name in dir(self):
            if name in to_skip:
                continue

            value = getattr(self, name)

            if isinstance(value, StoreObject):
                store_objects[name] = value
        return store_objects

    @property
    def counters(self):
        return {
            (value.name if hasattr(value, 'name') else '') or name: value
            for name, value in self.storables.items()
            if isinstance(value, Counter)
        }

    @property
    def case_generators(self):
        return {
            name: value
            for name, value in self.storables.items()
            if isinstance(value, CaseGenerator)
        }

    def calc_all(self, limit_to=None):
        """Calculate all counts and save calculated values into database.

        Already existing values will be updated.

        Args:
            limit_to: regular expression for limiting which counters should be executed
        """

        counters = {
            name: counter
            for name, counter in self.counters.items()
            if not limit_to or re.match(limit_to, name)
        }

        for name, counter in tqdm(counters.items(), total=len(counters)):

            count, new = get_or_create(self.storage_model, name=name)

            value = counter(self)
            count.value = value

            print(name, value)

            if new:
                db.session.add(count)

    def get_all(self):

        model = self.storage_model

        counts = {
            counter_name: db.session.query(model.value).filter(model.name == counter_name).scalar()
            for counter_name in self.counters.keys()
        }

        counts = {
            name: value if value is not None else self.default
            for name, value in counts.items()
        }

        return counts
