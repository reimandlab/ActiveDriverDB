from warnings import warn

from sqlalchemy.ext.declarative import declared_attr

from database import db


class Model(db.Model):
    """General abstract model"""
    __abstract__ = True

    id: int

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    @declared_attr
    def id(cls):
        return db.Column('id', db.Integer, primary_key=True)

    def __repr__(self):

        try:
            properties = {}

            for k, v in self.__dict__.items():
                if k.startswith('_'):
                    continue
                v = repr(v)
                if len(v) > 50:
                    v = v[:25] + '...' + v[-25:]
                properties[k] = v

            description = ', '.join(f'{k}={v}' for k, v in properties.items())

            return f'<{self.__class__.__name__}: {description}>'

        except Exception as e:
            warn(f'Could not generate repr for: {self} ({e}')
            return super().__repr__()
