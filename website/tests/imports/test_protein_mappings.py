from import_data import load_external_references
from database_testing import DatabaseTest
from models import Protein
from database import db
from miscellaneous import make_named_temp_file


# this is output of `head protein_mappings.tsv`
raw_protein_mappings = """\
	NM_012234	NP_036366	ENSP00000486012
	NM_001291281	NP_001278210	ENSP00000487155
			ENSP00000486069
INPP5D	NM_005541	NP_005532	ENSP00000486669
INPP5D	NM_001017915	NP_001017915	ENSP00000487191
INPP5D			ENSP00000487535
INPP5D			ENSP00000487335
INPP5D			ENSP00000486018
OBP2B	NM_014581	NP_055396	ENSP00000487521
OBP2B			ENSP00000486815\
"""


class TestImport(DatabaseTest):

    def test_protein_mappings(self):

        filename = make_named_temp_file(data=raw_protein_mappings)

        refseqs = [
            'NM_012234',    # present in reference mappings
            'NM_005541',    # present
            'NM_014581',    # present
            'NM_0001'       # not present in reference mappings
        ]

        proteins_we_have = {
            refseq_nm: Protein(refseq=refseq_nm)
            for refseq_nm in refseqs
        }

        with self.app.app_context():
            # let's pretend that we already have some proteins in our db
            db.session.add_all(proteins_we_have.values())

            references = load_external_references(filename)

        # there are 3 references we would like to have extracted
        # as we had three proteins in the db
        assert len(references) == 3

        protein = proteins_we_have['NM_012234']

        assert protein.external_references.uniprot_accession == ''
        assert protein.external_references.refseq_np == 'NP_036366'
        assert protein.external_references.ensembl_peptide == 'ENSP00000486012'

        protein = proteins_we_have['NM_005541']
        assert protein.external_references.uniprot_accession == 'INPP5D'

        # check if protein without references stays clear
        with self.app.app_context():
            protein = proteins_we_have['NM_0001']

            # it's needed to re-add the protein cause ORM will emit a query
            # (just in case, that's how flask-testing works - any object needs
            # to be re-added to session after its termination)
            db.session.add(protein)

            assert protein.external_references == None
