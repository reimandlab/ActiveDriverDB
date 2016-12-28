from view_testing import ViewTest
from models import Protein
from models import Gene
from database import db


test_gene_data = {
    'name': 'BRCA1',
    'isoforms': [
        Protein(
            refseq='NM_000123',
            sequence='TRAN',
        ),

    ]
}


class TestPGeneView(ViewTest):

    def test_show(self):

        g = Gene(**test_gene_data)
        db.session.add(g)

        response = self.client.get('/gene/show/BRCA1')

        assert response.status_code == 200
        assert b'BRCA1' in response.data
        assert b'NM_000123' in response.data
