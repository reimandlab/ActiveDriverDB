import pytest

from imports.protein_data import active_pathways_lists as active_pathways_lists_importer, ListData, pathway_identifiers
from imports.protein_data import pathways as pathways_importer
from database_testing import DatabaseTest
from miscellaneous import make_named_temp_file
from database import db
from models import TCGAMutation, SiteType, Pathway

raw_pathways_list = """\
term.id,term.name,adjusted.p.val,term.size,overlap
GO:0070268,cornification,0.000225929476177931,109,KRT17|KRT6A|KRT12|KRT16|KRT2|KRT10
GO:0043588,skin development,0.0022511036831041,404,KRT17|KRT6A|KRT12|KRT16|KRT2|SMAD4|BCL11B|KRT10
GO:0050801,ion homeostasis,0.0445298831877082,727,CASR|FGF23|SCN1B|UMOD|SNCA|KCNH2|PRNP|ANGPTL3|NOX1\
"""

# Excerpt from Gene Ontology
# Gene Ontology is licenced under Creative Commons Attribution 4.0 Unported License.
# https://creativecommons.org/licenses/by/4.0/legalcode
gmt_file = """\
GO:0061038	uterus morphogenesis	ASH1L	KDM5B	STRA6	WNT7A	WNT9B	NIPBL
GO:0048265	response to pain	TAC1	COMT	TSPO	SLC6A2	TRPA1	P2RX3	THBS4	TACR1	DBH	PRKCG	GCH1	NMUR2	P2RX4	EDNRB	THBS1	CACNA1A	CRH	CACNA1B	CAPN2	UCN	RET	SCN9A	VWA1	LPAR5	GJA4	P2RX2	RELN	TRPV1	NTRK1	PIRT
GO:0061366	behavioral response to chemical pain	P2RX3	NTRK1
GO:0061368	behavioral response to formalin induced pain	P2RX3	NTRK1
"""


class TestImport(DatabaseTest):

    def test_id_parsing(self):
        assert pathway_identifiers('GO:0070268') == {'gene_ontology': 70268}
        assert pathway_identifiers('REAC:R-HSA-1059683') == {'reactome': 1059683}
        assert pathway_identifiers('REAC:0000000') is None

    def test_gmt_parsing(self):
        filename = make_named_temp_file(gmt_file)

        with self.app.app_context():
            pathways = pathways_importer.load(filename)

        assert len(pathways) == 4

        morphogenesis = pathways[0]
        assert morphogenesis.description == 'uterus morphogenesis'
        assert len(morphogenesis.genes) == 6

    def test_pathways_lists(self):
        filename = make_named_temp_file(raw_pathways_list)

        with self.app.app_context():
            acetylation = SiteType(name='acetylation')
            db.session.add(acetylation)

            pathways = [
                Pathway(gene_ontology=70268, description='cornification'),
                Pathway(gene_ontology=43588, description='skin dev')    # note the altered name
            ]

            db.session.add_all(pathways)

            lists = [
                ListData(
                    name='TCGA list', path=filename, mutations_source=TCGAMutation,
                    site_type_name='acetylation'
                )
            ]

            with pytest.warns(UserWarning, match='pathway name differs'):
                pathways_lists = active_pathways_lists_importer.load(lists=lists)

        # one pathways list returned (TCGA)
        assert len(pathways_lists) == 1

        pathway_list = pathways_lists[0]

        # correct name of pathways list
        assert pathway_list.name == 'TCGA list'
        assert pathway_list.mutation_source_name == 'TCGA'
        assert pathway_list.site_type.name

        # let's take some entry
        an_entry = pathway_list.entries[0]

        assert type(an_entry.fdr) is float
        assert an_entry.overlap == {'KRT17', 'KRT6A', 'KRT12', 'KRT16', 'KRT2', 'KRT10'}
        assert an_entry.pathway_size == 109
        assert an_entry.pathway == pathways[0]

        pathways = {entry.pathway.gene_ontology for entry in pathway_list.entries}

        assert pathways == {70268, 43588, 50801}

        db.session.add_all(pathways_lists)

        with self.app.app_context():
            new_pathways = active_pathways_lists_importer.load(lists=[
                ListData(
                    name='TCGA list', path=filename, mutations_source=TCGAMutation,
                    site_type_name='acetylation'
                )
            ])

        # no duplicate lists should be created
        assert not new_pathways
