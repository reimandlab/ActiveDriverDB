from types import FunctionType, MethodType

from sqlalchemy import and_, or_
from sqlalchemy.ext.associationproxy import AssociationProxy
from sqlalchemy.sql.annotation import AnnotatedSelect
from sqlalchemy.sql.sqltypes import Text
from sqlalchemy.orm import RelationshipProperty

from database.types import ScalarSet
from helpers.utilities import is_iterable_but_not_str

from .basic_filter import BasicFilter


class SQLAlchemyAwareFilter(BasicFilter):
    """Extends python-side filtering by SQL filters generation

    Args:
        as_sqlalchemy:
            True if the filter should be executed on the SQL server side.

            A custom callback can be provided instead.
            The callback should accept a value of the filter as
            an argument and return an SQLAlchemy filter.
            The callback function will be called only if the
            filter is active (i.e. it has a non-default value).
        as_sqlalchemy_joins:
            if a custom as_sqlalchemy callback was provided and it
            requires any joins, the joins can be specified here.
    """

    sa_comparators = {
        'ge': '__ge__',
        'le': '__le__',
        'gt': '__gt__',
        'lt': '__lt__',
        'eq': '__eq__',
        'in': 'in_',
        'ni': 'notin_'
    }

    sa_join_operators = {
        'all': and_,
        'any': or_
    }

    def __init__(self, *args, as_sqlalchemy=None, as_sqlalchemy_joins=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_sqlalchemy = bool(as_sqlalchemy)

        if type(as_sqlalchemy) in [FunctionType, MethodType]:
            self.as_sqlalchemy_callback = as_sqlalchemy
        else:
            self.as_sqlalchemy_callback = None

        self.as_sqlalchemy_joins = as_sqlalchemy_joins or []

    def as_sqlalchemy(self, target):

        value = self.mapped_value

        if value is None:
            return None, []

        if self.as_sqlalchemy_callback:
            return self.as_sqlalchemy_callback(value), self.as_sqlalchemy_joins

        path = self.attribute.split('.')

        assert len(path) < 3     # we are unable to query deeper easily

        field = getattr(target, path[0])

        # Possible upgrade:
        #   from sqlalchemy.orm.attributes import QueryableAttribute
        #   if isinstance(field, QueryableAttribute):
        if type(field) is AnnotatedSelect:
            if self.comparator == 'eq':
                return field, []

        if type(field) is AssociationProxy:
            # additional joins may be needed when using proxies

            joins = []

            while type(field) is AssociationProxy:
                joins.append(field.target_class)
                field = field.remote_attr

            if self.comparator == 'in':

                if self.multiple == 'any':
                    # this wont give expected result for 'all'
                    func = getattr(field, self.sa_comparators[self.comparator])
                    return func(value), joins
                else:
                    # this works for 'any' too (but it's uglier)
                    func = getattr(field, '__eq__')

                    comp_func = self.sa_join_operators[self.multiple](
                        *[
                            func(sub_value)
                            for sub_value in value
                        ]
                    )
                    return comp_func, joins

        if len(path) == 2:
            if self.comparator == 'in':
                sub_attr = path[1]
                func = getattr(field, 'any')

                values = value if is_iterable_but_not_str(value) else [value]
                comp_func = self.sa_join_operators[self.multiple](
                    *[
                        func(**{sub_attr: sub_value})
                        for sub_value in values
                    ]
                )
                return comp_func, []

        comparator = self.sa_comparators[self.comparator]

        if self.comparator == 'in':
            if isinstance(field.property, RelationshipProperty):
                comparator = 'contains'
            elif type(field.property.columns[0].type) in [Text, ScalarSet]:
                comparator = 'like'
                value = '%' + value + '%'

        return getattr(field, comparator)(value), []
