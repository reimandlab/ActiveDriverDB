from sqlalchemy import inspect
from sqlalchemy.orm import aliased
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql.expression import func
from tqdm import tqdm

from berkley_db import BerkleyHashSet
from flask_sqlalchemy import SQLAlchemy
from genomic_mappings import GenomicMappings

db = SQLAlchemy()
bdb = GenomicMappings()
bdb_refseq = BerkleyHashSet()


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


def create_hybrid_expression(sql_func):

    def expression(parent_model, child_model, join=None):
        """
        Args:
            parent_model: owning entity (usually `cls`)
            child_model: entity on which the func will be evaluated
            join:
                a column to be joined on (for join between `child_model`
                and `parent_model`) or callable creating a join.
                Note: The join goes from child to parent.

        Returns:
            sqlalchemy expression for use in hybrid_property
        """
        parent_aliased = aliased(parent_model)

        query = db.session.query(child_model)

        if join:
            if callable(join):
                query = join(query)
            else:
                query = query.join(parent_aliased, join)
        return (
            query
            .filter(parent_aliased.id == parent_model.id)
            .statement.with_only_columns([sql_func]).order_by(None)
        )
    return expression


count_expression = create_hybrid_expression(func.count())


def update(model, **kwargs):
    db.session.query(model.__class__).filter_by(id=model.id).update(kwargs, synchronize_session=False)


def call_if_needed(value_or_callable, *args, **kwargs):
    if callable(value_or_callable):
        return value_or_callable(*args, **kwargs)
    else:
        return value_or_callable


def client_side_defaults(*columns):
    def decorator(init_func):
        def __init__(self, *args, **kwargs):
            columns_definitions = inspect(self.__class__).columns
            for key in columns:
                # if the user did not provide an alternative to the default
                if key not in kwargs:
                    default = columns_definitions[key].default.arg
                    kwargs[key] = call_if_needed(default, self)
            init_func(self, *args, **kwargs)
        return __init__
    return decorator


def create_key_model_dict(model, key, lowercase=False, options=None, progress=True):
    """Create 'entry.key: entry' dict mappings for all entries of given model.

    If `key` is a list, tuple or other iterable (but not str),
    a tuple of properties accessed with keys from such iterable
    is used as a key.
    """

    if isinstance(key, str):
        keys = [key]
    else:
        keys = list(key)

    entities = [
        getattr(model, key)
        for key in keys
    ]

    entities.append(model)

    query = db.session.query(*entities)

    if options:
        query = query.options(options)

    if progress:
        query = tqdm(query, total=query.count())

    if len(keys) > 1:
        assert not lowercase
        return {tuple(k): m for *k, m in query}

    if lowercase:
        return {k.lower(): m for k, m in query}
    else:
        return {k: m for k, m in query}


def get_engine(bind_key, app=None):
    if not app:
        from flask import current_app
        app = current_app
    return db.get_engine(app, bind_key)