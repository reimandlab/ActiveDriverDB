from sqlalchemy import DateTime, func, text, TypeDecorator, Text
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.ext.mutable import Mutable
from sqlalchemy.sql.functions import FunctionElement

from berkley_db import SetWithCallback


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


class ScalarSet(TypeDecorator):

    @property
    def python_type(self):
        return set

    impl = Text()

    def __init__(self, *args, separator=',', **kwargs):
        super().__init__(*args, **kwargs)
        self.separator = separator

    def process_bind_param(self, value, dialect):
        if not value:
            return ''
        assert all([self.separator not in v for v in value])
        return self.separator.join(value)

    def process_result_value(self, value, dialect):
        if not value:
            return set()
        return set(value.split(self.separator))

    def coerce_compared_value(self, op, value):
        return self.impl.coerce_compared_value(op, value)


class MutableSet(Mutable, SetWithCallback):

    def __init__(self, items):
        SetWithCallback.__init__(self, items, lambda s: self.changed())

    @classmethod
    def coerce(cls, key, value):
        """Convert plain set to MutableSet."""

        if not isinstance(value, MutableSet):
            if isinstance(value, set):
                return MutableSet(value)

            # this call will raise ValueError
            return Mutable.coerce(key, value)
        else:
            return value


MutableSet.associate_with(ScalarSet)

