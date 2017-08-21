from flask_testing import TestCase
from app import create_app
from database import db
from database import bdb
from database import bdb_refseq
from models import User


class DatabaseTest(TestCase):

    TESTING = True

    SQLALCHEMY_BINDS = {
        'cms': 'sqlite://',
        'bio': 'sqlite://'
    }

    BDB_DNA_TO_PROTEIN_PATH = '.test_databases/dtp.db'
    BDB_GENE_TO_ISOFORM_PATH = '.test_databases/gti.db'
    SQL_LEVENSTHEIN = False
    USE_LEVENSTHEIN_MYSQL_UDF = False

    SECRET_KEY = 'test_key'

    @property
    def config(self):
        return {
            key: getattr(self, key)
            for key in dir(self)
            if key.isupper()
        }

    def login(self, email='user@domain.org', password='strong-password', create=False, admin=False):
        if create:
            user = User(email, password, 10 if admin else 0)
            user.is_verified = True
            db.session.add(user)
            self.logged_user = user

        return self.client.post(
            '/login/',
            data={
                'email': email,
                'password': password,
            },
            follow_redirects=True
        )

    def logout(self, forget_user=True):
        result = self.client.get('/logout/', follow_redirects=True)
        if forget_user:
            db.session.delete(self.logged_user)
        self.logged_user = None
        return result

    def create_app(self):
        app = create_app(config_override=self.config)
        self.app = app
        return app

    def setUp(self):
        self.logged_user = None
        self.add_csrf_to_default_post()
        db.create_all()

    def add_csrf_to_default_post(self):
        old_client_post = self.client.post

        # this may be written with session_transaction instead,
        # but then I would have to nest three or five contexts
        # (app, login, session) in each test which is not DRY.
        @self.app.route('/get_testing_csrf_token')
        def testing_csrf():
            from flask import render_template_string
            return render_template_string('{{ csrf_token() }}')

        # add csrf token if requested
        def client_post(*args, with_csrf_token=True, **kwargs):

            if with_csrf_token:
                response = self.client.get('/get_testing_csrf_token')
                token = response.data

                if 'headers' not in kwargs:
                    kwargs['headers'] = {}

                kwargs['headers']['X-Csrftoken'] = token

            return old_client_post(*args, **kwargs)

        self.client.post = client_post

    def tearDown(self):

        db.session.remove()
        db.drop_all()
        bdb.drop()
        bdb_refseq.drop()
