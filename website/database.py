import os
from sqlalchemy.orm.exc import NoResultFound
from flask_sqlalchemy import SQLAlchemy
import bsddb3 as bsddb


db = SQLAlchemy()


def get_or_create(model, **kwargs):
    """Return a tuple: (object, was_created) for given parameters.

    Object will be taken from relational database (from a table corresponding
    to given `model`) or created if needed. Keyword arguments specify values of
    particular fields to be used in filtering or creation of the particular
    object. If there are more than one objects matching, a native SQLAlchemy
    exception will be raised.

    It's analagous with Django ORM function of the same name.
    """
    try:
        return model.query.filter_by(**kwargs).one(), False
    except NoResultFound:
        return model(**kwargs), True


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
        self.name = name
        self.open()

    def get_path(self):
        """Returns path to a file containing the database.

        The file is not guranted to exist.
        """
        base_dir = os.path.abspath(os.path.dirname(__file__))
        databases_dir = os.path.join(base_dir, 'databases')
        return os.path.join(databases_dir, self.name)

    def open(self, mode='c'):
        """Open hash database in a given mode.

        By default it opens a database in read-write mode and in case
        if a database of given name does not exists it creates one.
        """
        self.db = bsddb.hashopen(self.get_path(), mode)

    def __getitem__(self, key):
        """key: has to be str"""
        key = bytes(key, 'utf-8')
        try:
            items = list(
                filter(
                    bool,
                    self.db.get(key).decode('utf-8').split('|')
                )
            )
        except (KeyError, AttributeError):
            items = []

        return SetWithCallback(
            items,
            lambda new_set: self.__setitem__(key, new_set)
        )

    def __setitem__(self, key, items):
        """key: might be a str or bytes"""
        assert '|' not in items
        if not isinstance(key, bytes):
            key = bytes(key, 'utf-8')
        self.db[key] = bytes('|'.join(items), 'utf-8')

    def reset(self):
        """Reset database completely by removal. Assuming file == name."""
        os.remove(self.get_path())
        self.open()


def make_snv_key(chrom, pos, ref, alt):
    """Makes a key for given `snv` (Single Nucleotide Variation)

    to be used as a key in hashmap in snv -> csv mappings
    """
    return ':'.join((chrom, '%x' % int(pos.strip()))) + ref + alt


def decode_csv(value):
    value = value
    strand, ref, alt = value[:3]
    cdna_pos, exon, protein_id = value[3:].split(':')
    return dict(zip(
        ('strand', 'ref', 'alt', 'pos', 'cdna_pos', 'exon', 'protein_id'),
        (
            strand, ref, alt, (cdna_pos - 1) // 3 + 1,
            int(cdna_pos, base=16), exon, int(protein_id, base=16)
        )
    ))


def encode_csv(strand, ref, alt, pos, exon, protein_id):
    """Encode a Coding Sequence Variants into a single, short string.

    ref and alt are aminoacids, but pos is a position of mutation in cDNA, so
    aminoacid positions can be derived simply appling: (int(pos) - 1) // 3 + 1
    """
    item = strand + ref + alt + ':'.join((
        '%x' % int(pos), exon, '%x' % protein_id))
    return item


bdb = BerkleyHashSet('berkley_hash.db')
bdb_refseq = BerkleyHashSet('berkley_hash_refseq.db')
