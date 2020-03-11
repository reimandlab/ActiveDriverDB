import pytest

from imports.protein_data import active_pathways_lists as load_active_pathways_lists, ListData, pathway_identifiers
from database_testing import DatabaseTest
from miscellaneous import make_named_temp_file
from database import db
from models import TCGAMutation, SiteType, Pathway

raw_pathways_list = """\
term.id	term.name	adjusted.p.val	term.size	overlap
GO:0070268	cornification	0.000225929476177931	109	KRT17,KRT6A,KRT12,KRT16,KRT2,KRT10
GO:0043588	skin development	0.0022511036831041	404	KRT17,KRT6A,KRT12,KRT16,KRT2,SMAD4,BCL11B,KRT10
GO:0050801	ion homeostasis	0.0445298831877082	727	CASR,FGF23,SCN1B,UMOD,SNCA,KCNH2,PRNP,ANGPTL3,NOX1\
"""


class TestImport(DatabaseTest):

    def test_id_parsing(self):
        assert pathway_identifiers('GO:0070268') == {'gene_ontology': 70268}
        assert pathway_identifiers('REAC:R-HSA-1059683') == {'reactome': 1059683}
        assert pathway_identifiers('REAC:0000000') is None

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
                pathways_lists = load_active_pathways_lists(lists=lists)

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
            new_pathways = load_active_pathways_lists(lists=[
                ListData(
                    name='TCGA list', path=filename, mutations_source=TCGAMutation,
                    site_type_name='acetylation'
                )
            ])

        # no duplicate lists should be created
        assert not new_pathways
