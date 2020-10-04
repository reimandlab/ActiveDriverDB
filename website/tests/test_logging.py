import logging
from pathlib import Path
from tempfile import NamedTemporaryFile

from app import setup_logging


def test_logging():
    with NamedTemporaryFile(delete=False) as f:
        setup_logging(Path(f.name))

    logging.warning('Test warning 1')

    with open(f.name) as g:
        assert 'Test warning 1' in g.read()
