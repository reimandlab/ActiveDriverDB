from database import db
from .model_testing import ModelTest
from models import Cancer
from sqlalchemy.exc import IntegrityError
import pytest


class CancerTest(ModelTest):

    def test_init(self):

        cancer = Cancer(name='Bladder Urothelial Carcinoma',  code='BLCA')

        assert cancer.name == 'Bladder Urothelial Carcinoma'
        assert cancer.code == 'BLCA'

        db.session.add(cancer)

        the_same_code = Cancer(name='Colon adenocarcinoma',  code='BLCA')
        the_same_name = Cancer(name='Bladder Urothelial Carcinoma',  code='BRCA')

        with pytest.raises(IntegrityError):
            db.session.add(the_same_code)
            db.session.commit()

        # return to previous state, cancer needs to be re-added
        db.session.rollback()
        db.session.add(cancer)

        with pytest.raises(IntegrityError):
            db.session.add(the_same_name)
            db.session.commit()
