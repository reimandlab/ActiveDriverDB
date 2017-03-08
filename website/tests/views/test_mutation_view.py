from view_testing import ViewTest
from models import Mutation
from models import Protein
from models import Gene
from database import db


class TestMutationView(ViewTest):

    def test_show(self):

        p = Protein(refseq='NM_000123', sequence='TRAN', gene=Gene(name='TP53'))
        mutation = Mutation(protein=p, position=2, alt='K')

        db.session.add(mutation)

        response = self.client.get('/mutation/show/NM_000123/2/K')

        assert response.status_code == 200
        assert b'TP53' in response.data
        assert b'NM_000123' in response.data
