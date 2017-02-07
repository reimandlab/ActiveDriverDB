import os
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import OperationalError
from sqlalchemy.sql.expression import func
import bsddb3 as bsddb
from flask_sqlalchemy import SQLAlchemy


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


def has_or_any(field, *args, **kwargs):
    method = field.any if field.property.uselist else field.has
    return method(*args, **kwargs)


def get_highest_id(model):
    """Get the highest 'id' value from table corresponding to given model.

    It tries to get autoincrement value (if the database-driver supports this)
    or to manually find the highest id if autoincrement fetch fails. The first
    case is better because we will get reliable value for empty tables!

    If you do not want to relay on database-side autoincrement it might be
    usefull but not 100% reliable - you still need to worry about concurency.

    For _some_ neat cases it's the same as `model.query.count()` but if at
    least one record was manually removed the latter loses accuracy.
    """
    try:
        # let's try to fetch the autoincrement value. Since not all databases
        # will agree that we can do this and sometimes they might be fussy
        # when it comes to syntax, we assume it might fail. Severly.
        return get_autoincrement(model) - 1
    except OperationalError:
        # so if it has failed, let's try to find highest id the canonical way.
        return db.session.query(func.max(model.id)).scalar() or 0


def restart_autoincrement(model):
    """Restarts autoincrement counter"""
    from flask import current_app
    engine = db.get_engine(current_app, model.__bind_key__)
    db.session.close()
    engine.execute(
        'ALTER TABLE ' + model.__tablename__ + ' AUTO_INCREMENT = 1;'
    )


def get_autoincrement(model):
    """Fetch autoincrement value from database.

    It is database-engine dependent, might not work well with some drivers.
    """
    from flask import current_app
    engine = db.get_engine(current_app, model.__bind_key__)
    return engine.execute(
        'SELECT `AUTO_INCREMENT`' +
        ' FROM INFORMATION_SCHEMA.TABLES' +
        ' WHERE TABLE_SCHEMA = DATABASE()'
        ' AND TABLE_NAME = \'%s\';' % model.__tablename__
    ).scalar()


class SetWithCallback(set):
    """A set implementation that trigggers callbacks on `add` or `update`.

    It has an impotant use in BerkleyHashSet database implementation:
    it allows a user to modify sets like native Python's structures while all
    the changes are forwarded to the database, without addtional user's action.
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


class BerkleyHashSet:
    """A hash-indexed database where values are equivalent to Python's sets.

    It uses Berkley database for storage and accesses it through bsddb3 module.
    """

    def __init__(self, name):
        self.name = name
        self.path = self.create_path()
        self.open()

    def create_path(self):
        """Returns path to a file containing the database.

        The file is not guranted to exist, although the 'databases' directory
        will be created (if it does not exist).
        """
        base_dir = os.path.abspath(os.path.dirname(__file__))
        databases_dir = os.path.join(base_dir, 'databases')
        os.makedirs(databases_dir, exist_ok=True)
        return os.path.join(databases_dir, self.name)

    def open(self, mode='c'):
        """Open hash database in a given mode.

        By default it opens a database in read-write mode and in case
        if a database of given name does not exists it creates one.
        """
        self.db = bsddb.hashopen(self.path, mode)

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

    def __len__(self):
        return len(self.db)

    def reset(self):
        """Reset database completely by its removal and recreation."""
        os.remove(self.path)
        self.open()


def make_snv_key(chrom, pos, ref, alt):
    """Makes a key for given `snv` (Single Nucleotide Variation)

    to be used as a key in hashmap in snv -> csv mappings
    """
    return ':'.join(
        (chrom, '%x' % int(pos.strip()))
    ) + ref.lower() + alt.lower()


def decode_csv(encoded_data):
    """Decode Coding Sequence Variant data from string made by encode_csv()."""
    strand, ref, alt, is_ptm = encoded_data[:4]
    cdna_pos, exon, protein_id = encoded_data[4:].split(':')
    cdna_pos = int(cdna_pos, base=16)
    return dict(zip(
        (
            'strand', 'ref', 'alt', 'pos',
            'cdna_pos', 'exon', 'protein_id', 'is_ptm'
        ),
        (
            strand, ref, alt, (cdna_pos - 1) // 3 + 1,
            cdna_pos, exon, int(protein_id, base=16), bool(int(is_ptm))
        )
    ))


def encode_csv(strand, ref, alt, pos, exon, protein_id, is_ptm):
    """Encode a Coding Sequence Variants into a single, short string.

    ref and alt are aminoacids, but pos is a position of mutation in cDNA, so
    aminoacid positions can be derived simply appling: (int(pos) - 1) // 3 + 1
    """
    return strand + ref + alt + ('1' if is_ptm else '0') + ':'.join((
        '%x' % int(pos), exon, '%x' % protein_id))


bdb = BerkleyHashSet('berkley_hash.db')
bdb_refseq = BerkleyHashSet('berkley_hash_refseq.db')
