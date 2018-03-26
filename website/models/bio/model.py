from helpers.models import association_table_super_factory
from ..model import Model


class BioModel(Model):
    """Models descending from BioData are supposed to hold biology-related data

    and will be stored in a 'bio' database, separated from visualization
    settings and other data handled by 'content management system'.
    """
    __abstract__ = True
    __bind_key__ = 'bio'


make_association_table = association_table_super_factory(bind='bio')
