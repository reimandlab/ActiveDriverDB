import os
import bsddb3 as bsddb
from os.path import abspath
from os.path import basename
from os.path import dirname
from os.path import join


class SetWithCallback(set):
    """A set implementation that triggers callbacks on `add` or `update`.

    It has an important use in BerkleyHashSet database implementation:
    it allows a user to modify sets like native Python's structures while all
    the changes are forwarded to the database, without additional user's action.
    """
    _modifying_methods = {'update', 'add'}

    def __init__(self, items, callback):
        super().__init__(items)
        self.callback = callback
        for method_name in self._modifying_methods:
            method = getattr(self, method_name)
            setattr(self, method_name, self._wrap_method(method))

    def _wrap_method(self, method):
        def new_method_with_callback(*args, **kwargs):
            result = method(*args, **kwargs)
            self.callback(self)
            return result
        return new_method_with_callback


class BerkleyDatabaseNotOpened(Exception):
    pass


def require_open(func):
    def func_working_only_if_db_is_open(self, *args, **kwargs):
        if not self.is_open:
            raise BerkleyDatabaseNotOpened
        return func(self, *args, **kwargs)
    return func_working_only_if_db_is_open


class BerkleyHashSet:
    """A hash-indexed database where values are equivalent to Python's sets.

    It uses Berkley database for storage and accesses it through bsddb3 module.
    """

    def __init__(self, name=None):
        self.is_open = False
        if name:
            self.open(name)

    def _create_path(self):
        """Returns path to a file containing the database.

        The file is not guranted to exist, although the 'databases' directory
        will be created (if it does not exist).
        """
        base_dir = abspath(dirname(__file__))
        db_dir = join(base_dir, dirname(self.name))
        os.makedirs(db_dir, exist_ok=True)
        return join(db_dir, basename(self.name))

    def open(self, name, mode='c'):
        """Open hash database in a given mode.

        By default it opens a database in read-write mode and in case
        if a database of given name does not exists it creates one.
        """
        self.name = name
        self.path = self._create_path()
        self.db = bsddb.hashopen(self.path, mode, cachesize=20480 * 2)
        self.is_open = True

    def close(self):
        self.db.close()

    @require_open
    def __getitem__(self, key):
        """key: has to be str"""

        key = bytes(key, 'utf-8')
        try:
            items = filter(
                bool,
                self.db.get(key).decode('utf-8').split('|')
            )
        except (KeyError, AttributeError):
            items = []

        return SetWithCallback(
            items,
            lambda new_set: self.__setitem__(key, new_set)
        )

    def update(self, key, value):
        key = bytes(key, 'utf-8')
        try:
            items = set(
                filter(
                    bool,
                    self.db.get(key).split(b'|')
                )
            )
        except (KeyError, AttributeError):
            items = set()

        assert '|' not in value
        items.update((bytes(v, 'utf-8') for v in value))

        self.db[key] = b'|'.join(items)

    def add(self, key, value):
        key = bytes(key, 'utf-8')
        try:
            items = set(
                filter(
                    bool,
                    self.db.get(key).split(b'|')
                )
            )
        except (KeyError, AttributeError):
            items = set()

        assert '|' not in value
        items.add(bytes(value, 'utf-8'))

        self.db[key] = b'|'.join(items)

    @require_open
    def __setitem__(self, key, items):
        """key: can be a str or bytes"""

        assert '|' not in items
        if not isinstance(key, bytes):
            key = bytes(key, 'utf-8')
        self.db[key] = bytes('|'.join(items), 'utf-8')

    @require_open
    def __len__(self):
        return len(self.db)

    @require_open
    def drop(self):
        os.remove(self.path)

    @require_open
    def reset(self):
        """Reset database completely by its removal and recreation."""
        self.drop()
        self.open(self.name)

    @require_open
    def reload(self):
        self.close()
        self.open(self.name)
