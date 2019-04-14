from sqlalchemy import MetaData
from sqlalchemy.exc import SQLAlchemyError

from database import db, get_engine
from database.bulk import restart_autoincrement
from database.migrate import set_foreign_key_checks


def remove(orm_object, soft=False):
    """If soft, expunge given object from session, otherwise delete it."""
    if soft:
        return db.session.expunge(orm_object)
    else:
        return db.session.delete(orm_object)


def raw_delete_all(model):
    count = db.session.query(model).delete()
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
