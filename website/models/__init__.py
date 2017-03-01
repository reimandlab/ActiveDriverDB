from database import db
from sqlalchemy.ext.declarative import declared_attr


class Model(db.Model):
    """General abstract model"""
    __abstract__ = True

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    @declared_attr
    def id(cls):
        return db.Column('id', db.Integer, primary_key=True)


from .bio import *
from .cms import *
