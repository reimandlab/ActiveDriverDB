import gzip
from argparse import Namespace
from collections import defaultdict

from pytest import raises

from imports.protein_data import external_references as load_external_references
from database_testing import DatabaseTest
from models import Protein
from database import db
from miscellaneous import make_named_temp_file


idmapping_dat = """\
P68254-1	CCDS	CCDS25837.1
P68254-1	RefSeq	NP_035869.1
P68254-1	RefSeq_NT	NM_011739.3
P68254	UniGene	Mm.289630
P68254	BioGrid	204622
P68254	MINT	MINT-1520413
P68254	STRING	10090.ENSMUSP00000100067
P68254	Ensembl	ENSMUSG00000076432
P68254-1	Ensembl_TRS	ENSMUST00000049531
P68254-1	Ensembl_PRO	ENSMUSP00000106602
P68254-1	Ensembl_TRS	ENSMUST00000103002
P68254-1	Ensembl_PRO	ENSMUSP00000100067
P68254	GeneID	286863
Q5RFJ2	EMBL-CDS	CAH90155.1
Q5RFJ2	NCBI_TaxID	9601
Q5RFJ2	RefSeq	NP_001125044.1
Q5RFJ2	RefSeq_NT	NM_001131572.1
Q5RFJ2	RefSeq	XP_009235823.1
Q5RFJ2	RefSeq_NT	XM_009237548.1
Q5RFJ2	UniGene	Pab.7060
Q5RFJ2	STRING	9601.ENSPPYP00000014137
Q5RFJ2	Ensembl	ENSPPYG00000012663
Q5RFJ2	Ensembl_TRS	ENSPPYT00000014710
Q5RFJ2	Ensembl_PRO	ENSPPYP00000014137
Q5RFJ2	GeneID	100171925
Q5RFJ2	KEGG	pon:100171925
Q5RFJ2	eggNOG	KOG0841
Q5RFJ2	eggNOG	COG5040
Q5RFJ2	GeneTree	ENSGT00760000119116
Q5RFJ2	HOVERGEN	HBG050423
Q5RFJ2	KO	K16197
Q5RFJ2	OMA	WTSDNAT
Q5RFJ2	OrthoDB	EOG091G0VKY
Q5RFJ2	TreeFam	TF102002\
"""

duplicated_mappings = """\
P68254-1	CCDS	CCDS25837.1
P68254-1	RefSeq	NP_035869.1
P68254-1	RefSeq_NT	NM_011739.3
P68254-2	CCDS	CCDS25837.1
P68254-2	RefSeq	NP_035869.1
P68254-2	RefSeq_NT	NM_011739.3\
"""


class TestImport(DatabaseTest):

    def test_protein_references(self):

        filename = make_named_temp_file(data=idmapping_dat, opener=gzip.open, mode='wt')
        filename_dups = make_named_temp_file(data=duplicated_mappings, opener=gzip.open, mode='wt')

        refseqs = [
            'NM_011739',    # present in reference mappings
            'NM_001131572',    # present
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

            # there are 2 references we would like to have extracted
            # as we had three proteins in the db
            assert len(references) == 2

            protein = proteins_we_have['NM_011739']

            assert protein.external_references.uniprot_entries[0].accession == 'P68254'
            assert protein.external_references.refseq_np == 'NP_035869'
            assert protein.external_references.entrez_id == '286863'

            ensembl_peptides = protein.external_references.ensembl_peptides

            assert len(ensembl_peptides) == 2
            assert (
                set(ensembl.peptide_id for ensembl in ensembl_peptides) ==
                {'ENSMUSP00000106602', 'ENSMUSP00000100067'}
            )

            # check if protein without references stays clear
            protein = proteins_we_have['NM_0001']

            # it's needed to re-add the protein cause ORM will emit a query
            # (just in case, that's how flask-testing works - any object needs
            # to be re-added to session after its termination)
            db.session.add(protein)

            assert protein.external_references is None
