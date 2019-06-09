import lmdb


class LightningInterface:
    """Minimal, pythonic interface for lmdb"""

    def __init__(self, path, **kwargs):
        self.path = path
        self.env = lmdb.Environment(str(self.path), max_dbs=1, **kwargs)

    def get(self, key, default=None):
        with self.env.begin() as transaction:
            return transaction.get(key, default=default)

    def items(self):
        with self.env.begin() as transaction:
            cursor = transaction.cursor()
            for k, v in cursor:
                yield k, v

    def __setitem__(self, key, value):
        with self.env.begin(write=True) as transaction:
            return transaction.put(key, value)

    def __getitem__(self, item):
        with self.env.begin() as transaction:
            return transaction.get(item)

    def __len__(self):
        with self.env.begin() as transaction:
            return transaction.stat()['entries']

    def __contains__(self, item):
        indicator = object()
        with self.env.begin() as transaction:
            return transaction.get(item, default=indicator) is not indicator

    def close(self):
        self.env.close()
