import gzip
from argparse import Namespace
from collections import defaultdict

from pytest import raises

from imports.protein_data import external_references as load_external_references
from database_testing import DatabaseTest
from models import Protein, Gene
from database import db
from miscellaneous import make_named_temp_file


idmapping_dat = """\
P68251-1	RefSeq_NT	NM_011739.3
P68251	UniProtKB-ID	P68251_MOUSE
P68254	UniProtKB-ID	1433T_MOUSE
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

refseq_data = """\
#tax_id	GeneID	Symbol	RSG	LRG	RNA	t	Protein	p	Category
9606	29974	A1CF	NG_029916.1		NM_001198819.1		NP_001185748.1		reference standard
9606	29974	A1CF	NG_029916.1		NM_014576.3		NP_055391.2		aligned: Selected
9606	29974	A1CF	NG_029916.1		NM_138932.2		NP_620310.1		aligned: Selected
9606	29974	A1CF	NG_029916.1		NM_138933.2		NP_620311.1		aligned: Selected
9606	29974	A1CF	NG_029916.1		NM_001198818.1		NP_001185747.1		aligned: Selected
9606	29974	A1CF	NG_029916.1		NM_001198820.1		NP_001185749.1		aligned: Selected
9606	2	A2M	NG_011717.1		NM_000014.4		NP_000005.2		reference standard
9606	2	A2M	NG_011717.1		NM_000014.5		NP_000005.2		aligned: Selected
9606	2	A2M	NG_011717.1		NM_001347423.1		NP_001334352.1		aligned: Selected
9606	2	A2M	NG_011717.1		NM_001347424.1		NP_001334353.1		aligned: Selected
9606	2	A2M	NG_011717.1		NM_001347425.1		NP_001334354.1		aligned: Selected
9606	144568	A2ML1	NG_042857.1		NM_144670.5		NP_653271.2		reference standard
9606	144568	A2ML1	NG_042857.1		NM_001282424.2		NP_001269353.1		aligned: Selected
9606	53947	A4GALT	NG_007495.2		NM_017436.4		NP_059132.1		reference standard
9606	53947	A4GALT	NG_007495.2		NR_146459.1				aligned: Selected
"""

reflink_data = """\
#name	product	mrnaAcc	protAcc	geneName	prodName	locusLinkId	omimId
Mroh5	maestro heat-like repeat family member 5	NM_001033365	NP_001028537	258359	439734	268816	0
ppp1r8b	nuclear inhibitor of protein phosphatase 1	NM_201200	NP_957494	258360	393859	799896	0
"""


class TestImport(DatabaseTest):

    def test_protein_references(self):

        uniprot_filename = make_named_temp_file(data=idmapping_dat, opener=gzip.open, mode='wt')
        reflink_filename = make_named_temp_file(data=reflink_data, opener=gzip.open, mode='wt', suffix='.gz')
        refseq_filename = make_named_temp_file(data=refseq_data)

        refseqs = [
            'NM_011739',    # present in reference mappings
            'NM_001131572',    # present
            'NM_201200',    # present
            'NM_0001'       # not present in reference mappings
        ]

        g = Gene(name='Some gene')
        proteins_we_have = {
            refseq_nm: Protein(refseq=refseq_nm, gene=g)
            for refseq_nm in refseqs
        }

        with self.app.app_context():
            # let's pretend that we already have some proteins in our db
            db.session.add_all(proteins_we_have.values())

            references = load_external_references(uniprot_filename, refseq_filename, reflink_filename)

            # there are 3 references we would like to have extracted
            assert len(references) == 3

            protein = proteins_we_have['NM_011739']

            assert len(protein.external_references.uniprot_entries) == 2
            uniprot_entry = protein.external_references.uniprot_entries[1]
            assert uniprot_entry.accession == 'P68254'
            assert uniprot_entry.isoform == 1
            assert uniprot_entry.reviewed is True

            uniprot_entry = protein.external_references.uniprot_entries[0]
            assert uniprot_entry.reviewed is False
            # assert protein.external_references.refseq_np == 'NP_035869'
            # assert protein.external_references.entrez_id == '286863'

            ensembl_peptides = protein.external_references.ensembl_peptides

            assert len(ensembl_peptides) == 2
            assert (
                set(ensembl.peptide_id for ensembl in ensembl_peptides) ==
                {'ENSMUSP00000106602', 'ENSMUSP00000100067'}
            )

            protein = proteins_we_have['NM_001131572']

            assert len(protein.external_references.uniprot_entries) == 1
            uniprot_entry = protein.external_references.uniprot_entries[0]
            assert uniprot_entry.accession == 'Q5RFJ2'
            assert uniprot_entry.isoform == 1
            assert uniprot_entry.reviewed is False

            # check if protein without references stays clear
            protein = proteins_we_have['NM_0001']

            # it's needed to re-add the protein cause ORM will emit a query
            # (just in case, that's how flask-testing works - any object needs
            # to be re-added to session after its termination)
            db.session.add(protein)

            assert protein.external_references is None
