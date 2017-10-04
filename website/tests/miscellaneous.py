import gzip
from tempfile import NamedTemporaryFile

import pytest


def mock_proteins_and_genes(count):
    from database import db
    from models import Gene, Protein
    for i in range(count):
        g = Gene(name='Gene_%s' % i)
        p = Protein(refseq='NM_000%s' % i, gene=g)
        g.preferred_isoform = p
        db.session.add(g)


def make_named_temp_file(data=None, mode='w', opener=open, **kwargs):
    """Create temporary file and return path to it.

    Args:
        data: if given, the data will be written to file
        mode: mode in which file should be created (w, wb etc)
    """
    temp_file = NamedTemporaryFile(mode=mode, delete=False, **kwargs)

    temp_file.close()
    name = temp_file.name

    if data:
        with opener(name, mode) as f:
            f.write(data)

    return name


def make_named_gz_file(data=None, **kwargs):
    return make_named_temp_file(
        data=data, mode='wt', opener=gzip.open, suffix='.gz', **kwargs
    )


use_fixture = pytest.fixture(autouse=True)
