from view_testing import ViewTest
from models import Protein
from models import Gene
from database import db


class TestProteinView(ViewTest):

    def test_show(self):

        p = Protein(
            refseq='NM_000123',
            gene=Gene(name='SomeGene'),
            sequence='MAR'
        )

        db.session.add(p)
        db.session.commit()

        response = self.client.get('/protein/show/NM_000123')

        assert response.status_code == 200
        assert b'SomeGene' in response.data
        assert b'NM_000123' in response.data
        assert b'MAR' in response.data
