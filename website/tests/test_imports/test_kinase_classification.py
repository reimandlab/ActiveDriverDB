from imports.protein_data import kinase_classification as kinase_classification_importer
from database_testing import DatabaseTest
from miscellaneous import make_named_temp_file
from database import db
from models import Kinase
from models import KinaseGroup


# head data/regphos_kinome_scraped_clean.txt
# note: there are double tabulators between (Akt and AKT1) and (Akt and AKT2).
raw_gene_list = """\
No.	Kinase	Group	Family	Subfamily	Gene.Symbol	gene.clean	Description	group.clean
1	AKT1	AGC	Akt		AKT1	AKT1	v-akt murine thymoma viral oncogene homolog 1	Akt
2	AKT2	AGC	Akt		AKT2	AKT2	v-akt murine thymoma viral oncogene homolog 2	Akt
3	AKT3	AGC	Akt		AKT3	AKT3	v-akt murine thymoma viral oncogene homolog 3 (protein kinase B, gamma)	Akt
4	CRIK	AGC	DMPK	CRIK	CIT	CIT	citron (rho-interacting, serine/threonine kinase 21)	DMPK_CRIK
5	DMPK1	AGC	DMPK	GEK	DMPK	DMPK	dystrophia myotonica-protein kinase	DMPK_GEK\
"""


class TestImport(DatabaseTest):

    def test_classification(self):
        """Following assertion about data file holds:
            - 'family' fits better to our 'group' than any other column
            - 'gene.clean', not 'Kinase' is being used as kinase name as it fits much better.
        """

        existing_kinases = {
            name: Kinase(name=name)
            for name in ('AKT1', 'Akt2', 'CIT')
        }

        existing_groups = {
            name: KinaseGroup(name=name)
            for name in ('Akt', )
        }

        def add_to_session():
            db.session.add_all(existing_kinases.values())
            db.session.add_all(existing_groups.values())

        filename = make_named_temp_file(raw_gene_list)

        add_to_session()

        with self.app.app_context():
            new_groups = kinase_classification_importer.load(filename)

        assert len(new_groups) == 1
        new_group = new_groups[0]

        assert new_group.name == 'DMPK'

        add_to_session()

        assert len(new_group.kinases) == 2
        assert existing_kinases['CIT'] in new_group.kinases

        old_group = existing_groups['Akt']
        assert len(old_group.kinases) == 3

        assert existing_kinases['AKT1'] in old_group.kinases
        assert existing_kinases['Akt2'] in old_group.kinases
