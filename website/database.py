from flask_sqlalchemy import SQLAlchemy
import bsddb3 as bsddb


db = SQLAlchemy()


class SetWithCallback(set):

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


class BerkleyHashSet:

    def __init__(self, name):
        # open hash database in read-write mode (create it if does not exists)
        self.db = bsddb.hashopen(name, 'c')

    def __getitem__(self, key):
        """
        key: has to be str
        """
        key = bytes(key, 'utf-8')
        try:
            items = list(filter(bool, self.db.get(key).decode('utf-8').split('|')))
        except (KeyError, AttributeError):
            items = []

        return SetWithCallback(
            items,
            lambda new_set: self.__setitem__(key, new_set)
        )

    def __setitem__(self, key, items):
        """key: might be a str or bytes
        """
        assert '|' not in items
        if not isinstance(key, bytes):
            key = bytes(key, 'utf-8')
        self.db[key] = bytes('|'.join(items), 'utf-8')


def make_snv_key(chrom, pos, ref, alt):
    return ':'.join((chrom, '%x' % int(pos.strip()))) + ref + alt


def decode_csv(value):
    value = value
    strand, ref, alt = value[:3]
    pos, exon, protein_id = value[3:].split(':')
    return dict(zip(
        ('strand', 'ref', 'alt', 'pos', 'exon', 'protein_id'),
        (strand, ref, alt, int(pos, base=16), exon, int(protein_id, base=16))
    ))


def encode_csv(strand, ref, alt, pos, exon, protein_id):
    item = strand + ref + alt + ':'.join((
        '%x' % int(pos), exon, '%x' % protein_id))
    return item


bdb = BerkleyHashSet('databases/berkley_hash.db')
bdb_refseq = BerkleyHashSet('databases/berkley_hash_refseq.db')
