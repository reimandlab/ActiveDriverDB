"""Implementation of filters to be used with Ajax and URL based queries"""

from .sqlalchemy_filter import SQLAlchemyAwareFilter
from .manager import FilterManager

Filter = SQLAlchemyAwareFilter

__all__ = (
    Filter,
    FilterManager
)
