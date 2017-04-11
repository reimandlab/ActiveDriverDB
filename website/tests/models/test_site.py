import pytest
from database import db
from model_testing import ModelTest

from exceptions import ValidationError
from models import Protein
from models import Site


class SiteTest(ModelTest):

    def test_consistency(self):

        p = Protein(refseq='NM_007', id=1, sequence='ABCD')
        db.session.add(p)

        # matching residue
        assert Site(position=1, type='methylation', residue='B', protein=p)

        # mismatched residue
        with pytest.raises(ValidationError):
            Site(position=2, type='methylation', residue='B', protein=p)

        # no residue and position in range
        assert Site(position=2, protein=p)

        # no residue and position outside of range
        with pytest.raises(ValidationError):
            Site(position=5, protein=p)
        with pytest.raises(ValidationError):
            Site(position=-5, protein=p)

