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
        bdb.drop()
        bdb_refseq.drop()
