from argparse import Namespace
from collections import defaultdict

from imports.protein_data import external_references as load_external_references
from database_testing import DatabaseTest
from models import Protein
from database import db
from miscellaneous import make_named_temp_file


# this is output of `head protein_external_references.tsv -n 50 | tail -n 10`.
# entrez ids were made up later
raw_protein_mappings = """\
NM_007100	P56385	NP_009031	1	ENSP00000306003
NM_000335	Q14524	NP_000326	2	ENSP00000398266
NM_001317946		NP_001304875	3	ENSP00000340883 ENSP00000486780
NM_000337	Q92629	NP_000328	4	ENSP00000338343
NM_007104	P62906	NP_009035	5	ENSP00000363018
NM_000339	P55017	NP_000330	6	ENSP00000402152
NM_000338	Q13621	NP_000329	7	ENSP00000370381
NM_007109	Q9Y242	NP_009040	8	ENSP00000393875 ENSP00000383252 ENSP00000397160 ENSP00000399388 ENSP00000414980 ENSP00000401548 ENSP00000365433
NM_007108	Q15370	NP_009039	9	ENSP00000386652
NM_001012969	Q6DHV7	NP_001311296	10	ENSP00000374302\
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
        assert protein.external_references.entrez_id == 2

        # check if protein without references stays clear
        with self.app.app_context():
            protein = proteins_we_have['NM_0001']

            # it's needed to re-add the protein cause ORM will emit a query
            # (just in case, that's how flask-testing works - any object needs
            # to be re-added to session after its termination)
            db.session.add(protein)

            assert protein.external_references is None

    def test_reference_download(self):
        from data.get_external_references import save_references
        from data.get_external_references import get_references
        from data.get_external_references import dataset
        from data.get_external_references import add_references

        filename = make_named_temp_file()
        fake_references = {
            'NM_001': {'ensembl': 'ENSG00001', 'entrez': '1'},
            'NM_002': {'ensembl': 'ENSG00002', 'entrez': '2'},
        }
        save_references(fake_references, ('entrez', 'ensembl'), path=filename)

        with open(filename) as f:
            contents = f.readlines()
            # order is not important when exporting reference data,
            # but the structure (tabs, newlines) is.
            assert contents in (
                ['NM_001\t1\tENSG00001\n', 'NM_002\t2\tENSG00002'],
                ['NM_002\t2\tENSG00002\n', 'NM_001\t1\tENSG00001']
            )

        fake_search_results = 'NM_01\tENSG_01\nNM_02\tENSG_02'
        dataset.search = lambda x: Namespace(text=fake_search_results)

        assert get_references('refseq', 'ensembl') == [
            'NM_01\tENSG_01',
            'NM_02\tENSG_02'
        ]

        fake_search_results = 'NM_01\tENSG_01\t1\nNM_02\tENSG_02\t2\nXX_03\tENSG_03\t3\nNM_004'
        dataset.search = lambda x: Namespace(text=fake_search_results)
        references = defaultdict(dict)
        add_references(references, 'refseq', ['ensembl', 'entrez'], primary_id_prefix='NM_')

        # rows where primary ids are not prefixed with 'NM_' (third)
        # and where there is essentially no data (fourth) should be skipped
        assert len(references) == 2
        assert references['NM_01'] == {'ensembl': 'ENSG_01', 'entrez': '1'}
        assert references['NM_02'] == {'ensembl': 'ENSG_02', 'entrez': '2'}
