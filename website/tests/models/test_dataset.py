from database import db
from model_testing import ModelTest
from models import User
from models import UsersMutationsDataset


test_query = """\
HTR3E I183823756M
STAT6 W737C
chr12 57490358 C A\
"""


class DatasetTest(ModelTest):

    def test_init(self):

        from views.search import MutationSearch

        search = MutationSearch(text_query=test_query)
        user = User('user@domain', 'password')

        dataset = UsersMutationsDataset(
            name='test',
            data=search,
            owner=user
        )

        db.session.add(dataset)
        db.session.commit()

        dataset.assign_randomized_id()
        db.session.commit()

        public_id = dataset.randomized_id

        d = UsersMutationsDataset.query.filter_by(randomized_id=public_id).one()

        assert d == dataset

        assert dataset.data
        assert dataset.query_size == 3

        # should be empty as no mutations where imported
        assert not dataset.mutations

        assert dataset.name == 'test'

        from datetime import timedelta
        assert dataset.life_expectancy < timedelta(days=7)
