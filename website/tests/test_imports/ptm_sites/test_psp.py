import gzip
from pathlib import Path
from tempfile import TemporaryDirectory

from database import db
from database_testing import DatabaseTest
from imports.sites.psp import PhosphoSitePlusImporter
from miscellaneous import make_named_gz_file
from models import Protein


MAPPINGS = """\
P01258	RefSeq_NT	NM_001741.2
P01258	RefSeq_NT	NM_001033952.2
P13796-1	RefSeq_NT	NM_002298.4
"""


CANONICAL = """\
>sp|P01258|CALC_HUMAN Calcitonin OS=Homo sapiens GN=CALCA PE=1 SV=2
MGFQKFSPFLALSILVLLQAGSLHAAPFRSALESSPADPATLSEDEARLLLAALVQNYVQ
MKASELEQEQEREGSSLDSPRSKRCGNLSTCMLGTYTQDFNKFHTFPQTAIGVGAPGKKR
DMSSDLERDHRPHVSMPQNAN
>sp|P13796|PLSL_HUMAN Plastin-2 OS=Homo sapiens GN=LCP1 PE=1 SV=6
MARGSVSDEEMMELREAFAKVDTDGNGYISFNELNDLFKAACLPLPGYRVREITENLMAT
"""

ALTERNATIVE = """\
>sp|P01258-2|CALC_HUMAN Isoform 2 of Calcitonin OS=Homo sapiens GN=CALCA
MGFQKFSPFLALSILVLLQAGSLHAAPFRSALESSPADPATLSEDEARLLLAALVQNYVQ
MKASELEQEQEREGSSLDSPRSKRCGNLSTCMLGTYTQDFNKFHTFPQTAIGVGAPGKKR
DMSSDLERDHRPHNHCPEESL
>sp|P13796-2|PLSL_HUMAN Isoform 2 of Plastin-2 OS=Homo sapiens GN=LCP1
MCAEDGDSKFSMSISMNSPFLEILHLENCNYAVELGKNQAKFSLVGIGGQDLNEGNRTLT
"""


SITES = """\
110817
PhosphoSitePlus(R) (PSP) was created by Cell Signaling Technology Inc. It is licensed under a Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported License. When using PSP data or analyses in printed publications or in online resources, the following acknowledgements must be included: (a) the words "PhosphoSitePlus(R), www.phosphosite.org" must be included at appropriate places in the text or webpage, and (b) the following citation must be included in the bibliography: "Hornbeck PV, Zhang B, Murray B, Kornhauser JM, Latham V, Skrzypek E PhosphoSitePlus, 2014: mutations, PTMs and recalibrations. Nucleic Acids Res. 2015 43:D512-20. PMID: 25514926."

GENE	PROTEIN	ACC_ID	HU_CHR_LOC	MOD_RSD	SITE_GRP_ID	ORGANISM	MW_kD	DOMAIN	SITE_+/-7_AA	LT_LIT	MS_LIT	MS_CST	CST_CAT#
CALCA	CALCA	P01258	11p15.2	T105-ga	27911933	human	15.47	Calc_CGRP_IAPP	QDFNKFHtFPQtAIG		1		
CALCA	CALCA	P01258	11p15.2	T109-ga	27911936	human	15.47	Calc_CGRP_IAPP	KFHtFPQtAIGVGAP		1		
"""


KINASES = """\
110817
Data extracted from PhosphoSitePlus(R), created by Cell Signaling Technology Inc. PhosphoSitePlus is licensed under a Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported License. Attribution must be given in written, oral and digital presentations to PhosphoSitePlus, www.phosphosite.org. Written documents should additionally cite Hornbeck PV, Kornhauser JM, Tkachev S, Zhang B, Skrzypek E, Murray B, Latham V, Sullivan M (2012) PhosphoSitePlus: a comprehensive resource for investigating the structure and function of experimentally determined post-translational modifications in man and mouse. Nucleic Acids Res. 40, D261�70.; www.phosphosite.org.

GENE	KINASE	KIN_ACC_ID	KIN_ORGANISM	SUBSTRATE	SUB_GENE_ID	SUB_ACC_ID	SUB_GENE	SUB_ORGANISM	SUB_MOD_RSD	SITE_GRP_ID	SITE_+/-7_AA	DOMAIN	IN_VIVO_RXN	IN_VITRO_RXN	CST_CAT#
PRKCD	PKCD	Q05655	human	L-plastin	3936	P13796	LCP1	human	S5	450852	___MARGsVsDEEMM		X	 	
"""


class TestImport(DatabaseTest):

    def test_import(self):
        protein = Protein(
            refseq='NM_001741',
            sequence='MGFQKFSPFLALSILVLLQAGSLHAAPFRSALESSPADPATLSEDEARLLLAALVQNYVQMKASELEQEQEREGSSLDSPRSKRCGNLSTCMLGTYTQDFNKFHTFPQTAIGVGAPGKKRDMSSDLERDHRPHVSMPQNAN*'
        )

        db.session.add(protein)

        with TemporaryDirectory() as dir_path:
            dir_path = Path(dir_path)

            with gzip.open(dir_path / 'O-GalNAc_site_dataset.gz', 'wt') as f:
                f.write(SITES)

            with gzip.open(dir_path / 'Kinase_Substrate_Dataset.gz', 'wt') as f:
                f.write(KINASES)

            importer = PhosphoSitePlusImporter(
                make_named_gz_file(CANONICAL),
                make_named_gz_file(ALTERNATIVE),
                make_named_gz_file(MAPPINGS),
                dir_path=dir_path
            )

            sites = importer.load_sites(site_datasets=['O-GalNAc'])

            assert len(sites) == 2

            sites_by_pos = {site.position: site for site in sites}

            assert sites_by_pos[105].residue == sites_by_pos[109].residue == 'T'
            assert sites_by_pos[105].type == {'glycosylation'}
