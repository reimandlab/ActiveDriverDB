from view_testing import ViewTest

from database import db
from models import Gene
from models import Protein

test_query = "chr18 19282310 T C"


class TestSearchView(ViewTest):

    def test_search_proteins(self):
        from views.search import search_proteins

        # create 15 genes and proteins
        for i in range(15):
            g = Gene(name='Gene_%s' % i)
            p = Protein(refseq='NM_000%s' % i, gene=g)
            g.preferred_isoform = p
            db.session.add(g)

        assert not search_proteins('TP53')

        results = search_proteins('Gene', 10)

        assert results
        assert len(results) == 10

        assert results[0].name.startswith('Gene')

        # should not be case sensitive
        results = search_proteins('gene', 1)
        assert results

        # the same for refseq search
        assert search_proteins('NM_0003', 1)
        assert search_proteins('nm_0003', 1)
        assert search_proteins('0003', 1)

        assert not search_proteins('9999', 1)

        #
        # test actual view
        #
        response = self.client.get('/search/proteins?proteins=Gene_2', follow_redirects=True)

        assert response.status_code == 200
        assert b'Gene_2' in response.data
        assert b'NM_0002' in response.data

    def search_mutations(self, **data):
        return self.client.post(
            '/search/mutations',
            data=data
        )

    def test_save_search(self):

        self.login('user@domain.org', 'password', create=True)

        save_response = self.search_mutations(
            mutations=test_query,
            store_on_server=True,
            dataset_name='Test Dataset'
        )

        assert save_response.status_code == 200

        # if user saved a dataset, it should be listed in his datasets
        browse_response = self.client.get('/my_datasets/')
        assert b'Test Dataset' in browse_response.data

        self.logout()

        # it's still allowed to save data on server without logging in,
        # but then user will not be able to browse these as datasets.
        unauthorized_save_response = self.search_mutations(
            mutations=test_query,
            store_on_server=True,
            dataset_name='Test Dataset'
        )

        assert unauthorized_save_response.status_code == 200
