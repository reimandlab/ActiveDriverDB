from imports.protein_data import load_external_references
from database_testing import DatabaseTest
from models import Protein
from database import db
from miscellaneous import make_named_temp_file


# this is output of `head protein_external_references.tsv -n 50 | tail -n 10`
raw_protein_mappings = """\
NM_007100	P56385	NP_009031	ENSP00000306003
NM_000335	Q14524	NP_000326	ENSP00000398266
NM_001317946		NP_001304875	ENSP00000340883 ENSP00000486780
NM_000337	Q92629	NP_000328	ENSP00000338343
NM_007104	P62906	NP_009035	ENSP00000363018
NM_000339	P55017	NP_000330	ENSP00000402152
NM_000338	Q13621	NP_000329	ENSP00000370381
NM_007109	Q9Y242	NP_009040	ENSP00000393875 ENSP00000383252 ENSP00000397160 ENSP00000399388 ENSP00000414980 ENSP00000401548 ENSP00000365433
NM_007108	Q15370	NP_009039	ENSP00000386652
NM_001012969	Q6DHV7	NP_001311296	ENSP00000374302\
"""


class TestImport(DatabaseTest):

    def test_protein_references(self):

        filename = make_named_temp_file(data=raw_protein_mappings)

        refseqs = [
            'NM_007100',    # present in reference mappings
            'NM_000335',    # present
            'NM_001317946',    # present
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

        protein = proteins_we_have['NM_001317946']

        assert protein.external_references.uniprot_accession == ''
        assert protein.external_references.refseq_np == 'NP_001304875'
        ensembl_peptides = protein.external_references.ensembl_peptides

        assert len(ensembl_peptides) == 2
        assert (
            set(ensembl.peptide_id for ensembl in ensembl_peptides) ==
            {'ENSP00000340883', 'ENSP00000486780'}
        )

        protein = proteins_we_have['NM_000335']
        assert protein.external_references.uniprot_accession == 'Q14524'

        # check if protein without references stays clear
        with self.app.app_context():
            protein = proteins_we_have['NM_0001']

            # it's needed to re-add the protein cause ORM will emit a query
            # (just in case, that's how flask-testing works - any object needs
            # to be re-added to session after its termination)
            db.session.add(protein)

            assert protein.external_references is None
