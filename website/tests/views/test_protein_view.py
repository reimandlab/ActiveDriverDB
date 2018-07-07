from view_testing import ViewTest, relative_location
from models import Protein
from models import Site
from database import db
from test_sequence import test_protein_data, create_test_mutations


class TestProteinView(ViewTest):

    def test_browse(self):
        p = Protein(**test_protein_data())
        db.session.add(p)

        response = self.client.get('/protein/browse', follow_redirects=True)

        assert response.status_code == 200

    def test_redirect(self):

        p = Protein(**test_protein_data())
        db.session.add(p)

        response = self.client.get('/protein/show/NM_000123?filters=Mutation.sources:in:MC3')
        assert response.status_code == 302
        assert relative_location(response) == '/sequence/show/NM_000123?filters=Mutation.sources:in:MC3'

    def test_sites(self):

        p = Protein(**test_protein_data())

        sites = [
            Site(position=3, residue='R', type={'phosphorylation'}),
            Site(position=4, residue='T', type={'methylation'})
        ]
        db.session.add(p)
        p.sites = sites

        response = self.client.get('/protein/sites/NM_000123')

        assert response.status_code == 200
        assert response.content_type == 'application/json'

        assert len(response.json) == 2

        phosphorylation_site_repr = None

        for site_repr in response.json:
            print(site_repr)
            if site_repr['type'] == 'phosphorylation':
                phosphorylation_site_repr = site_repr

        assert phosphorylation_site_repr

    def test_mutation(self):

        p = Protein(**test_protein_data())
        p.mutations = create_test_mutations()
        db.session.add(p)

        queries = {
            '/protein/mutation/NM_000123/1/K': 1,
            '/protein/mutation/NM_000123/1/K?filters=Mutation.sources:in:MC3': 1,
            '/protein/mutation/NM_000123/2/K': 1,
        }
        for query, expected_results_cnt in queries.items():
            response = self.client.get(query)
            assert len(response.json) == expected_results_cnt

        response = self.client.get('/protein/mutation/NM_000123/2/K?filters=Mutation.sources:in:MC3')
        assert 'Warning: There is a mutation, but it does not satisfy given filters' in response.json

        response = self.client.get('/protein/mutation/NM_000123/2/K')
        mut = response.json.pop()
        assert mut['ref'] == 'A'
        assert mut['pos'] == 2
        assert mut['alt'] == 'K'
        assert mut['protein'] == 'NM_000123'

    def test_known_mutations(self):

        p = Protein(**test_protein_data())
        p.mutations = create_test_mutations()
        db.session.add(p)

        response = self.client.get('/protein/known_mutations/NM_000123')
        muts = response.json
        assert len(muts) == 4
