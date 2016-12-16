from flask_testing import TestCase
from app import create_app
from database import db


class ModelTest(TestCase):

    SQLALCHEMY_BINDS = {
        'cms': 'sqlite://',
        'bio': 'sqlite://'
    }
    TESTING = True

    @property
    def config(self):
        return {
            key: getattr(self, key)
            for key in dir(self)
            if key.isupper()
        }

    def create_app(self):
        return create_app(config_override=self.config)

    def setUp(self):

        db.create_all()

    def tearDown(self):

        db.session.remove()
        db.drop_all()
