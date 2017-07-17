from view_testing import ViewTest
from models import Protein, GeneList, TCGAMutation, Mutation, MC3Mutation
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


class TestGeneView(ViewTest):

    def test_show(self):

        g = Gene(**test_gene_data)
        db.session.add(g)

        response = self.client.get('/gene/show/BRCA1')

        assert response.status_code == 200
        assert b'BRCA1' in response.data
        assert b'NM_000123' in response.data

    def test_browse_list(self):

        from miscellaneous import make_named_temp_file
        from test_imports.test_gene_list import raw_gene_list
        from imports.protein_data import active_driver_gene_lists as load_active_driver_gene_lists

        filename = make_named_temp_file(raw_gene_list)

        # create gene list and genes
        with self.app.app_context():
            from imports.protein_data import ListData
            gene_lists = load_active_driver_gene_lists(lists=(
                ListData(name='TCGA', path=filename, mutations_source=TCGAMutation),
            ))
        db.session.add_all(gene_lists)

        # create preferred isoforms for genes
        for i, gene in enumerate(Gene.query.all()):
            # at least one mutation is required for gene on a gene list to be displayed
            mut = Mutation()
            MC3Mutation(mutation=mut)

            p = Protein(refseq='NM_000%s' % i, mutations=[mut])
            gene.isoforms = [p]
            gene.preferred_isoform = p

        # check the static template
        response = self.client.get('/gene/list/TCGA')
        assert response.status_code == 200
        assert b'TCGA' in response.data

        # check the dynamic data
        response = self.client.get('/gene/list_data/TCGA?order=asc')
        assert response.status_code == 200

        gene_list = GeneList.query.filter_by(name='TCGA').one()

        # all results retrieved
        assert response.json['total'] == len(gene_list.entries)

        # properly sorted by fdr
        fdrs = [row['fdr'] for row in response.json['rows']]
        assert fdrs == sorted(fdrs)

    def test_browse(self):
        genes = []

        gene_names = ('BRCA1', 'BRCA2', 'TP53')
        for i, name in enumerate(gene_names):
            p = Protein(refseq='NM_000%s' % i)
            gene = Gene(name=name, isoforms=[p], preferred_isoform=p)
            genes.append(gene)

        db.session.add_all(genes)

        # check the static template
        response = self.client.get('/gene/browse/')
        assert response.status_code == 200

        # check the dynamic data
        response = self.client.get('/gene/browse_data/')
        assert response.status_code == 200

        assert response.json['total'] == len(genes)
