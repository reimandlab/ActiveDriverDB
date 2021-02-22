from flask import url_for

from database import db
from models import Pathway, Gene, GeneList, GeneListEntry, PathwaysList, PathwaysListEntry
from view_testing import ViewTest


def create_pathways():

    # mock data
    genes = [Gene(name=name) for name in 'KRAS NRAS AKAP13 NF1 BCR'.split()]
    significant_genes = [Gene(name=name) for name in 'TP53 AKT1 TXN GPI AKT3 FN TSC1'.split()]

    pathways = {
        'TP53 regulation': Pathway(
            description='TP53 Regulates Transcription of DNA Repair Genes',
            reactome=6796648,
            genes=genes + significant_genes
        ),
        'Small pathway': Pathway(
            description='A pathway with more than 5 significant genes but less than 10 at all',
            reactome=679,
            genes=significant_genes
        ),
        'Ras GO': Pathway(
            description='Ras protein signal transduction',
            gene_ontology=33277,
            genes=genes
        ),
    }
    db.session.add_all(pathways.values())
    return locals()


def create_gene_list(created):
    gene_list = GeneList(
        name='ClinVar',
        entries=[
            GeneListEntry(gene=gene, fdr=0.001, p=0.001)
            for gene in created['significant_genes']
        ],
        mutation_source_name='ClinVar'
    )
    db.session.add(gene_list)
    db.session.commit()

    return gene_list


def create_pathways_list(created):
    overlap = {gene.name for gene in created['significant_genes']}
    pathways = created['pathways']
    pathways_list = PathwaysList(
        name='Pathways enriched in germline mutations',
        mutation_source_name='ClinVar',
        entries=[
            PathwaysListEntry(
                pathway=pathways['TP53 regulation'],
                fdr=0.15,
                overlap=overlap,  # seven significant genes
                pathway_size=12
            ),
            PathwaysListEntry(
                pathway=pathways['Small pathway'],
                fdr=0.01,
                overlap=overlap,
                pathway_size=7
            )
        ]
    )
    db.session.add(pathways_list)
    db.session.commit()
    return pathways_list


class TestPathwaysView(ViewTest):

    def test_details(self):
        create_pathways()

        response = self.client.get('/pathways/details/?gene_ontology_id=33277')
        pathway = response.json
        assert pathway['description'] == 'Ras protein signal transduction'
        assert len(pathway['genes']) == 5

    def test_with_significant_genes(self):
        created = create_pathways()

        gene_list = create_gene_list(created)

        response = self.client.get('/pathways/with_significant_genes/')
        assert response.status_code == 200

        response = self.client.get(f'/pathways/significant_data/{gene_list.id}')

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

    def test_list(self):
        created = create_pathways()
        pathways = created['pathways']

        pathways_list = create_pathways_list(created)

        response = self.client.get('/pathways/lists/')
        assert response.status_code == 200

        response = self.client.get(f'/pathways/list/{pathways_list.name}')
        assert response.status_code == 200

        response = self.client.get(f'/pathways/list_data/{pathways_list.id}')

        # only one pathway has FDR lower than 0.1
        assert response.json['total'] == 1

        pathway = response.json['rows'].pop()

        assert pathway['description'] == pathways['Small pathway'].description

        # test filtering
        response = self.client.get(f'/pathways/list_data/{pathways_list.id}?search=A pathway with more than')
        assert response.json['total'] == 1
        response = self.client.get(f'/pathways/list_data/{pathways_list.id}?search=pathway&order=asc&offset=0&limit=25')
        assert response.json['total'] == 1

        response = self.client.get(f'/pathways/list_data/{pathways_list.id}?search=TP53')
        assert response.json['total'] == 0

    def test_index(self):
        created = create_pathways()
        pathways_list = create_pathways_list(created)
        gene_list = create_gene_list(created)

        response = self.client.get('/pathways/')
        assert response.status_code == 200
        html = response.data.decode()

        assert url_for('PathwaysView:list', pathways_list_name=pathways_list.name) in html
        assert url_for('PathwaysView:with_significant_genes', significant_gene_list_name=gene_list.name) in html

    def test_show_pathway(self):
        create_pathways()
        response = self.client.get('/pathways/reactome/6796648')
        assert response.status_code == 200
        html = response.data
        assert b'TP53 Regulates Transcription of DNA Repair Genes' in html

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
