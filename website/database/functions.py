from sqlalchemy import Numeric, func, DateTime, text
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement


class least(FunctionElement):
    type = Numeric()
    name = 'least'


class greatest(FunctionElement):
    type = Numeric()
    name = 'greatest'


@compiles(least)
def default_least(element, compiler, **kw):
    return compiler.visit_function(element)


@compiles(greatest)
def default_greatest(element, compiler, **kw):
    return compiler.visit_function(element)


@compiles(least, 'sqlite')
def sqlite_least(element, compiler, **kw):
    return compiler.visit_function(func.min(*element.clauses))


@compiles(greatest, 'sqlite')
def sqlite_greatest(element, compiler, **kw):
    return compiler.visit_function(func.max(*element.clauses))


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

