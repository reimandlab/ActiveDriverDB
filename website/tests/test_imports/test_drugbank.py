from typing import Dict

from database import db
from database_testing import DatabaseTest
from imports.protein_data import drugbank

from models import Gene
from models.bio.drug import Drug

# Excerpt derived from DrugBank, which is distributed under
# Creative Common’s Attribution-NonCommercial 4.0 International License
# https://creativecommons.org/licenses/by-nc/4.0/legalcode
# Note:
# Pathways are left on purpose as they have nested <drug> and <drugbank-id> tags
# which should not confuse the parser.
DRUG_BANK_SUBSET_PATH = 'tests/test_imports/drugbank_subset.xml'


class TestImport(DatabaseTest):

    def test_drugbank(self):
        f2 = Gene(name='F2')
        egfr = Gene(name='EGFR')

        # these three genes are targets of Etanercept,
        # however they are all grouped as a single target,
        # thus we need to make sure that the parser
        # loads associations for all of them
        c10qa = Gene(name='C1QA')
        c10qb = Gene(name='C1QB')
        c10qc = Gene(name='C1QC')

        db.session.add_all([
            f2, egfr,
            c10qa, c10qb, c10qc
        ])

        drugs = drugbank.load(DRUG_BANK_SUBSET_PATH)

        # the third drug (Dornase alfa) does not have a known protein target
        assert len(drugs) == 3

        drugs = Drug.query.all()

        drugs_by_name: Dict[str, Drug] = {
            drug.name: drug
            for drug in drugs
        }
        # first drug
        lepirudin = drugs_by_name['Lepirudin']

        lep_groups = list(lepirudin.groups)
        assert len(lep_groups) == 1
        assert lep_groups[0].name == 'approved'
        assert lepirudin.target_genes == [f2]

        # second drug
        assert len(egfr.targeted_by) == 1
        assert egfr.targeted_by[0].drug.name == 'Cetuximab'
        assert drugs_by_name['Cetuximab'].type.name == 'biotech'

        # third drug
        etanercep = drugs_by_name['Etanercept']
        assert etanercep.target_genes == [c10qa, c10qb, c10qc]

