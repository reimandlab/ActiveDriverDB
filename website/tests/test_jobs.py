import time

from database import update, db
from database.functions import utc_now
from database_testing import DatabaseTest
from jobs import hard_delete_expired_datasets
from models import User, UsersMutationsDataset
from test_models.test_dataset import create_test_dataset


class JobTest(DatabaseTest):

    def test_hard_delete_dataset(self):
        user = User('user@domain', 'password')

        # let's create five datasets
        datasets = []
        for _ in range(5):
            datasets.append(create_test_dataset(owner=user))

        # and make two of them expired
        for dataset in datasets[:2]:
            update(dataset, store_until=utc_now())

        db.session.commit()
        time.sleep(2)

        removed_cnt = hard_delete_expired_datasets()

        # two were removed, three remained
        assert removed_cnt == 2
        assert UsersMutationsDataset.query.count() == 3
