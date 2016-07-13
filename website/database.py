from flask_sqlalchemy import SQLAlchemy
import bsddb3 as bsddb


db = SQLAlchemy()


class BerkleyHashSet:

    def __init__(self, name):
        # open hash database in read-write mode (create it if does not exists)
        self.db = bsddb.hashopen(name, 'c')

    def __getitem__(self, key):
        key = bytes(key, 'utf-8')
        return self.db.get(key, b'').split(b'|')

    def __setitem__(self, key, items):
        assert '|' not in items
        key = bytes(key, 'utf-8')
        self.db[key] = b'|'.join(items)


bdb = BerkleyHashSet('databases/berkley_hash.db')
