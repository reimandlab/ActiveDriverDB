from warnings import warn

from sqlalchemy import func, MetaData
from sqlalchemy.orm import aliased
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.sql.expression import func
from flask_sqlalchemy import SQLAlchemy
from berkley_db import BerkleyHashSet
from helpers.parsers import chunked_list

db = SQLAlchemy()
bdb = BerkleyHashSet()
bdb_refseq = BerkleyHashSet()


def get_engine(bind_key, app=None):
    if not app:
        from flask import current_app
        app = current_app
    return db.get_engine(app, bind_key)


def remove(orm_object, soft=False):
    """If soft, expunge given object from session, otherwise delete it."""
    if soft:
        return db.session.expunge(orm_object)
    else:
        return db.session.delete(orm_object)


def get_or_create(model, **kwargs):
    """Return a tuple: (object, was_created) for given parameters.

    Object will be taken from relational database (from a table corresponding
    to given `model`) or created if needed. Keyword arguments specify values of
    particular fields to be used in filtering or creation of the particular
    object. If there are more than one objects matching, a native SQLAlchemy
    exception will be raised.

    It's analogous with Django ORM function of the same name.
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
    useful but not 100% reliable - you still need to worry about concurrency.

    For _some_ neat cases it's the same as `model.query.count()` but if at
    least one record was manually removed the latter loses accuracy.
    """
    try:
        # let's try to fetch the autoincrement value. Since not all databases
        # will agree that we can do this and sometimes they might be fussy
        # when it comes to syntax, we assume it might fail. Severely.
        return get_autoincrement(model) - 1
    except OperationalError:
        # so if it has failed, let's try to find highest id the canonical way.
        return db.session.query(func.max(model.id)).scalar() or 0


def restart_autoincrement(model):
    """Restarts autoincrement counter"""
    engine = get_engine(model.__bind_key__)
    db.session.close()
    if db.session.bind.dialect.name == 'sqlite':
        warn(UserWarning('Sqlite increment reset is not supported'))
        return
    engine.execute(
        'ALTER TABLE ' + model.__tablename__ + ' AUTO_INCREMENT = 1;'
    )


def get_autoincrement(model):
    """Fetch autoincrement value from database.

    It is database-engine dependent, might not work well with some drivers.
    """
    engine = get_engine(model.__bind_key__)
    return engine.execute(
        'SELECT `AUTO_INCREMENT`' +
        ' FROM INFORMATION_SCHEMA.TABLES' +
        ' WHERE TABLE_SCHEMA = DATABASE()'
        ' AND TABLE_NAME = \'%s\';' % model.__tablename__
    ).scalar()


def make_snv_key(chrom, pos, ref, alt):
    """Makes a key for given `snv` (Single Nucleotide Variation)
    to be used as a key in hashmap in snv -> csv mappings.

    Args:
        chrom:
            str representing one of human chromosomes
            (like '1', '22', 'X'), e.g. one of returned
            by `helpers.bioinf.get_human_chromosomes`
        pos:
            int representing position of variation
        ref:
            char representing reference nucleotide
        alt:
            char representing alternative nucleotide
    """
    return ':'.join(
        (chrom, '%x' % int(pos))
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


def levenshtein_sorted(sql_query, column, query):
    from flask import current_app
    from sqlalchemy import desc
    if current_app.config['SQL_LEVENSTHEIN']:
        sql_query = sql_query.order_by(
            desc(
                func.levenshtein_ratio(func.lower(column), query.lower())
            )
        )
    return sql_query


def encode_csv(strand, ref, alt, pos, exon, protein_id, is_ptm):
    """Encode a Coding Sequence Variants into a single, short string.

    ref and alt are aminoacids, but pos is a position of mutation in cDNA, so
    aminoacid positions can be derived simply applying: (int(pos) - 1) // 3 + 1
    """
    return strand + ref + alt + ('1' if is_ptm else '0') + ':'.join((
        '%x' % int(pos), exon, '%x' % protein_id))


def fast_count(query):
    return query.session.execute(
        query.statement.with_only_columns([func.count()]).order_by(None)
    ).scalar()


def yield_objects(base_query, step_size=1000):
    done = False
    step = 0
    while not done:
        obj = None
        for obj in base_query.limit(step_size).offset(step * step_size):
            yield obj
        step += 1
        done = not obj


def raw_delete_all(model):
    count = model.query.delete()
    return count


def remove_model(model, delete_func=raw_delete_all, autoincrement_func=restart_autoincrement):
    print('Removing %s:' % model.__name__)
    try:
        count = delete_func(model)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        print('Removing failed')
        raise
    autoincrement_func(model)
    print('Removed %s entries of %s' % (count, model.__name__))


def set_foreign_key_checks(engine, active=True):
    if db.session.bind.dialect.name == 'sqlite':
        warn(UserWarning('Sqlite foreign key checks managements is not supported'))
        return
    engine.execute('SET FOREIGN_KEY_CHECKS=%s;' % 1 if active else 0)


def reset_relational_db(app, **kwargs):

    name = kwargs.get('bind', 'default')

    print('Removing', name, 'database...')
    engine = get_engine(name, app)
    set_foreign_key_checks(engine, active=False)
    db.session.commit()
    db.reflect()
    db.session.commit()
    meta = MetaData()
    meta.reflect(bind=engine)
    for table in reversed(meta.sorted_tables):
        engine.execute(table.delete())
    set_foreign_key_checks(engine, active=True)
    print('Removing', name, 'database completed.')

    print('Recreating', name, 'database...')
    db.create_all(**kwargs)
    print('Recreating', name, 'database completed.')


def get_column_names(table):
    return set((i.name for i in table.c))


def bulk_ORM_insert(model, keys, data):
    for chunk in chunked_list(data):
        db.session.bulk_insert_mappings(
            model,
            [
                dict(zip(keys, entry))
                for entry in chunk
            ]
        )
        db.session.flush()


def bulk_raw_insert(table, keys, data, bind=None):
    engine = get_engine(bind)
    for chunk in chunked_list(data):
        engine.execute(
            table.insert(),
            [
                dict(zip(keys, entry))
                for entry in chunk
            ]
        )
        db.session.flush()


def count_expression(parent_model, child_model, join_column=None):
    parent_aliased = aliased(parent_model)

    query = db.session.query(child_model)
    if join_column:
        query = query.join(parent_aliased, join_column)
    return (
        query.
            filter(parent_aliased.id == parent_model.id).
            statement.with_only_columns([func.count()]).order_by(None)
    )
