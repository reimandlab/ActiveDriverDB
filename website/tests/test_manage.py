from manage import automigrate
from argparse import Namespace


def test_automigrate():
    """Simple blackbox test for automigrate."""
    args = Namespace(databases=('bio', 'cms'))
    result = automigrate(args)
    assert result
