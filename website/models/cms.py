from website.database import db
from sqlalchemy.ext.hybrid import hybrid_method
from sqlalchemy.ext.hybrid import hybrid_property
from werkzeug.utils import cached_property


class Model(db.Model):
    """Default model configuration to be used across whole file.

    Models descending from Model are supposed to hold visualisation
    settings and other data handled by 'content managment system'.
    """
    __bind_key__ = 'cms'  # use 'cms' database (specified in `config.py` file)


class User(Model):
    """Model for use with Flask-Login"""
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, index=True)

    def __repr__(self):
        return '<User {0} with id {1}>'.format(
            self.name,
            self.id
        )
