from website import security
from website.database import db
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.hybrid import hybrid_method
from sqlalchemy.ext.hybrid import hybrid_property
from werkzeug.utils import cached_property


class Model:
    """Default model configuration to be used across whole file.

    Models descending from Model are supposed to hold visualisation
    settings and other data handled by 'content managment system'.
    """
    @declared_attr
    def __bind_key__(cls):
        """Always use 'cms' database (specified in `config.py` file)."""
        return 'cms'

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    @declared_attr
    def id(cls):
        return db.Column('id', db.Integer, primary_key=True)


class User(db.Model, Model):
    """Model for use with Flask-Login"""

    # http://www.rfc-editor.org/errata_search.php?rfc=3696&eid=1690
    email = db.Column(db.String(254), unique=True)
    pass_hash = db.Column(db.String(256))

    def __init__(self, email, password):
        self.email = email
        self.pass_hash = security.generate_secret_hash(password)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def authenticate(self, password):
        return security.verify_secret(password, str(self.pass_hash))

    @cached_property
    def username(self):
        return self.email.split('@')[0].replace('.', ' ').title()

    def __repr__(self):
        return '<User {0} with id {1}>'.format(
            self.email,
            self.id
        )


class Page(db.Model, Model):
    """Model representing a single CMS page"""

    address = db.Column(db.String(256), unique=True, index=True)
    title = db.Column(db.String(256))
    content = db.Column(db.Text())

    def __repr__(self):
        return '<Page {0} with id {1}>'.format(
            self.address,
            self.id
        )
