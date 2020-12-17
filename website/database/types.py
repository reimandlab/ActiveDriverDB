from io import StringIO

from pandas import DataFrame, read_csv
from sqlalchemy import TypeDecorator, Text
from sqlalchemy.dialects import mysql
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.ext.mutable import MutableSet

from database import db
from pandas.util import hash_pandas_object


class DataFrameStore(TypeDecorator):
    """"""

    impl = Text

    def process_bind_param(self, value: DataFrame, dialect):
        from io import StringIO
        stream = StringIO()
        value.to_csv(stream)
        return stream.getvalue()

    def compare_values(self, x, y):
        return sum(hash_pandas_object(x)) == sum(hash_pandas_object(y))

    def process_result_value(self, value: str, dialect) -> DataFrame:
        stream = StringIO(value)
        return read_csv(stream)

    def copy(self, **kw):
        return DataFrameStore(self.impl.length)


class ScalarSet(TypeDecorator):

    @property
    def python_type(self):
        return set

    impl = Text

    def __init__(self, *args, separator=',', element_type=str, empty_indicator='{}', coerce=None, **kwargs):
        """A column mimicking a Python set on top of Text column.

        Args:
            *args: passed to Text type constructor
            separator: a character or set of character used as separator during serialization
            element_type: type of the element to be stored (all elements have to be of the same type)
            empty_indicator: a string used to indicate that the set is empty
            coerce: a set of rules for coercion from types other than element types;
                    each rule should map a type to object's property which will be
                    used instead of the object; it has to be of element_type type.
                    The purpose of having coerce rules separate from element_type is to
                    enable support for multiple types/rules simultaneously.
            **kwargs: passed to Text type constructor
        """
        super().__init__(*args, **kwargs)
        self.separator = separator
        self.type = element_type
        self.empty_indicator = empty_indicator
        self.coerce_rules = coerce or {}

    @property
    def comparator_factory(self):

        coerce_element = self.coerce_element

        class Comparator(self.impl.Comparator):

            def operate(self, op, *other, **kwargs):
                return super().operate(op, *[coerce_element(e) for e in other], **kwargs)

        return Comparator

    def process_bind_param(self, value, dialect):
        if not value:
            return self.empty_indicator

        value = [self.coerce_element(v) for v in value]

        assert all(isinstance(v, self.type) for v in value)

        if not isinstance(self.type, str):
            value = list(map(str, value))

        assert all([self.separator not in v for v in value])

        return self.separator.join(value)

    def process_result_value(self, value, dialect):
        if not value or value == self.empty_indicator:
            return set()
        return set(map(self.type, value.split(self.separator)))

    def coerce_element(self, element):
        for value_type, attribute in self.coerce_rules.items():
            if isinstance(element, value_type):
                return getattr(element, attribute)
        return element

    def coerce_compared_value(self, op, value):
        return self.impl.coerce_compared_value(op, value)


MutableSet.associate_with(ScalarSet)


class MediumPickle(db.PickleType):

    impl = mysql.MEDIUMBLOB


@compiles(MediumPickle, 'sqlite')
def sqlite_utc_after(element, compiler, **kwargs):
    return compiler.visit_BLOB(element, **kwargs)
