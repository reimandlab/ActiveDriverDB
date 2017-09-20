from warnings import warn

from sqlalchemy import MetaData
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import aliased
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql.expression import func, FunctionElement, text
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import DateTime

from berkley_db import BerkleyHashSet
from flask_sqlalchemy import SQLAlchemy
from genomic_mappings import GenomicMappings
from helpers.parsers import chunked_list

db = SQLAlchemy()
bdb = GenomicMappings()
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

    Warning: this function may emit a rollback. Commit your changes before use!
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
    if engine.dialect.name == 'sqlite':
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


def join_unique(query, model):
    joined_tables = [mapper.class_ for mapper in query._join_entities]
    if model not in joined_tables:
        return query.join(model)
    return query


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
        query
        .filter(parent_aliased.id == parent_model.id)
        .statement.with_only_columns([func.count()]).order_by(None)
    )


class utc_now(FunctionElement):
    """This is based on a template provided by SQLAlchemy documentation. Please see:
    http://docs.sqlalchemy.org/en/latest/core/compiler.html#utc-timestamp-function
    """
    type = DateTime()


@compiles(utc_now, 'mysql')
def mysql_utc_now(element, compiler, **kwargs):
    """
    This is not UTC but is stored internally as UTC.
    I lost several hours trying to use UTC_TIMESTAMP
    but it appears that it is not possible to set is as default:
    https://dba.stackexchange.com/questions/20217/mysql-set-utc-time-as-default-timestamp
    """
    return 'CURRENT_TIMESTAMP'


@compiles(utc_now, 'sqlite')
def sqlite_utc_now(element, compiler, **kwargs):
    return "(datetime('now'))"


class utc_days_after(FunctionElement):
    type = DateTime()
    name = 'utc_days_after'


@compiles(utc_days_after, 'mysql')
def mysql_utc_after(element, compiler, **kwargs):
    days, = list(element.clauses)
    return compiler.process(func.date_add(utc_now(), text('interval %s day' % days.value)))


@compiles(utc_days_after, 'sqlite')
def sqlite_utc_after(element, compiler, **kwargs):
    days, = list(element.clauses)
    return "(datetime('now', '+%s day'))" % days.value


def update(model, **kwargs):
    db.session.query(model.__class__).filter_by(id=model.id).update(kwargs, synchronize_session=False)


def add_column(engine, table_name, definition):
    sql = 'ALTER TABLE `%s` ADD %s' % (table_name, definition)
    engine.execute(sql)


def drop_column(engine, table_name, column_name):
    sql = (
        'ALTER TABLE `%s` DROP `%s`'
        % (table_name, column_name)
    )
    engine.execute(sql)


def update_column(engine, table_name, column_definition):
    sql = (
        'ALTER TABLE `%s` MODIFY COLUMN %s'
        % (table_name, column_definition)
    )
    engine.execute(sql)
