from flask_testing import TestCase
from app import create_app
from database import db
from models import User


class DatabaseTest(TestCase):

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

    def login(self, email, password, create=False):
        if create:
            user = User(email, password)
            db.session.add(user)

        return self.client.post(
            '/login/',
            data={
                'email': email,
                'password': password,
            },
            follow_redirects=True
        )

    def logout(self):
        return self.client.get('/logout/', follow_redirects=True)

    def create_app(self):
        app = create_app(config_override=self.config)
        self.app = app
        return app

    def setUp(self):

        db.create_all()

    def tearDown(self):

        db.session.remove()
        db.drop_all()
