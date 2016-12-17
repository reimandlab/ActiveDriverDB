from manage import automigrate
from argparse import Namespace
from database_testing import DatabaseTest


class ManageTest(DatabaseTest):

    def test_automigrate(self):
        """Simple blackbox test for automigrate."""
        args = Namespace(databases=('bio', 'cms'))
        result = automigrate(args)
        assert result
