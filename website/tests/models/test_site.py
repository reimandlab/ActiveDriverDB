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

        # matching residue (note: for sites, positions are 1-based)
        assert Site(position=2, type='methylation', residue='B', protein=p)

        # mismatched residue
        with pytest.raises(ValidationError):
            Site(position=3, type='methylation', residue='B', protein=p)

        # no residue and position in range
        assert Site(position=2, protein=p)

        # no residue and position outside of range
        with pytest.raises(ValidationError):
            Site(position=5, protein=p)
        with pytest.raises(ValidationError):
            Site(position=-5, protein=p)

    def test_sequence(self):

        p = Protein(refseq='NM_007', id=1, sequence='ABCDEFGHIJKLMNOPQRSTUVWXYZ')
        db.session.add(p)

        data = {
            0: '-------ABCDEFGH',
            10: 'DEFGHIJKLMNOPQR',
            25: 'STUVWXYZ-------'
        }

        for position, expected_sequence in data.items():
            site = Site(position=position + 1, type='methylation', residue=p.sequence[position], protein=p)
            assert site.sequence == expected_sequence
