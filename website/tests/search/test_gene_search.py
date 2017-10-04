from database_testing import DatabaseTest
from search.gene import GeneNameSearch
from tests.miscellaneous import mock_proteins_and_genes


class TestGeneSearch(DatabaseTest):

    def test_refseq(self):
        from search.gene import RefseqGeneSearch

        # create 15 genes and proteins
        mock_proteins_and_genes(10)

        search = RefseqGeneSearch().search

        # negative control
        for phase in ['9999', 'NM_00000', 'Gene']:
            assert not search(phase)

        # limiting
        results = search('NM_', limit=5)
        assert len(results) == 5

        assert results[0].name.startswith('Gene')

        # test the search itself
        for refseq in ['NM_0003', 'nm_0003', '0003']:
            results = search(refseq)
            assert len(results) == 1
            assert results[0].name == 'Gene_3'

            isoforms = results[0].matched_isoforms
            assert len(isoforms) == 1
            assert isoforms.pop().refseq == 'NM_0003'

    def test_gene_symbol(self):
        from search.gene import SymbolGeneSearch

        # create 15 genes and proteins
        mock_proteins_and_genes(10)

        search = SymbolGeneSearch().search

        # negative control
        assert not search('TP53')   # symbol absent
        assert not search('NM_0000')   # refseq not a symbol

        # limiting
        results = search('Gene', limit=5)
        assert len(results) == 5

        assert results[0].name.startswith('Gene')

        # should not be case sensitive
        results = search('gene')
        assert results

        # should ignore flanking whitespaces
        for query in ('gene ', 'gene   ', ' gene', ' gene '):
            assert search(query)

    def test_gene_name(self):
        # this is exactly the same as gene_symbol
        mock_proteins_and_genes(6)

        search = GeneNameSearch().search
        results = search('Full name of gene', limit=5)

        assert len(results) == 5
        assert results[0].full_name.startswith('Full name of gene')
