from database_testing import DatabaseTest
from models import Gene
from models import Mutation
from models import PotentialMutation
from models import CancerMutation
from models import MIMPMutation
from database import db


class ManageTest(DatabaseTest):

    LOAD_STATS = False

    def test_count(self):
        from statistics import Statistics
        genes = [Gene(name='TEST1'), Gene(name='TEST2')]
        db.session.add_all(genes)
        assert Statistics.count(Gene) == 2

    def test_count_mappings(self):
        from statistics import Statistics
        from database import bdb
        bdb['some_thing'] = 'Test1'
        bdb['some_other_thing'] = 'Test2'
        bdb['some_thing'] = 'Test2'
        assert Statistics.count_mappings() == 2
