from warnings import warn

from sqlalchemy import func
from sqlalchemy.exc import OperationalError

from database import db, get_engine
from helpers.parsers import chunked_list


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


def bulk_orm_insert(model, keys, data):
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
