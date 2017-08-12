from database import db
from models import Pathway, Gene, GeneList, GeneListEntry
from view_testing import ViewTest


def create_pathways():

    # not necessarily true ;)
    genes = [Gene(name=name) for name in 'KRAS NRAS AKAP13 NF1 BCR'.split()]
    significant_genes = [Gene(name=name) for name in 'TP53 AKT1 TXN GPI AKT3 FN TSC1'.split()]

    pathways = [
        Pathway(
            description='TP53 Regulates Transcription of DNA Repair Genes',
            reactome=6796648,
            genes=genes + significant_genes
        ),
        Pathway(
            description='A pathway with more than 5 significant genes but less than 10 at all',
            reactome=679,
            genes=significant_genes
        ),
        Pathway(
            description='Ras protein signal transduction',
            gene_ontology=33277,
            genes=genes
        ),
    ]
    db.session.add_all(pathways)
    return locals()


class TestPathwaysView(ViewTest):

    def test_details(self):
        create_pathways()

        response = self.client.get('/pathways/details/?gene_ontology_id=33277')
        pathway = response.json
        assert pathway['description'] == 'Ras protein signal transduction'
        assert len(pathway['genes']) == 5

    def test_with_significant_genes(self):
        created = create_pathways()

        gene_list = GeneList(
            name='ClinVar',
            entries=[
                GeneListEntry(gene=gene, fdr=0.001, p=0.001)
                for gene in created['significant_genes']
            ])
        db.session.add(gene_list)
        db.session.commit()

        response = self.client.get('/pathways/with_significant_genes/')
        assert response.status_code == 200

        response = self.client.get('/pathways/significant_data/%s' % gene_list.id)

        # only one pathway has more than 10 genes with at least 5 of them significant
        assert response.json['total'] == 1

        pathway = response.json['rows'].pop()
        expected_values = {
            'reactome': 6796648,
            'description': 'TP53 Regulates Transcription of DNA Repair Genes',
            'significant_genes_count': 7,
            'gene_count': 12,
            'ratio': 7 / 12,
        }
        for key, value in expected_values.items():
            assert pathway[key] == value

    def test_any_pathway(self):
        create_pathways()
        db.session.commit()

        response = self.client.get('/pathways/all/')
        assert response.status_code == 200

        # all pathways should be selected
        response = self.client.get('/pathways/all_data/')
        assert response.json['total'] == 3

        # is search working?
        response = self.client.get('/pathways/all_data/?search=Ras protein')
        assert response.json['total'] == 1
        pathway = response.json['rows'].pop()
        assert pathway['description'] == 'Ras protein signal transduction'
