import gzip
from tempfile import TemporaryDirectory

from database import db
from database_testing import DatabaseTest
from imports.sites.psp import PhosphoSitePlusImporter
from miscellaneous import make_named_gz_file
from models import Protein


MAPPINGS = """\
P01258	RefSeq_NT	NM_001741.2
P01258	RefSeq_NT	NM_001033952.2
"""


CANONICAL = """\
>sp|P01258|CALC_HUMAN Calcitonin OS=Homo sapiens GN=CALCA PE=1 SV=2
MGFQKFSPFLALSILVLLQAGSLHAAPFRSALESSPADPATLSEDEARLLLAALVQNYVQ
MKASELEQEQEREGSSLDSPRSKRCGNLSTCMLGTYTQDFNKFHTFPQTAIGVGAPGKKR
DMSSDLERDHRPHVSMPQNAN
"""

ALTERNATIVE = """\
>sp|P01258-2|CALC_HUMAN Isoform 2 of Calcitonin OS=Homo sapiens GN=CALCA
MGFQKFSPFLALSILVLLQAGSLHAAPFRSALESSPADPATLSEDEARLLLAALVQNYVQ
MKASELEQEQEREGSSLDSPRSKRCGNLSTCMLGTYTQDFNKFHTFPQTAIGVGAPGKKR
DMSSDLERDHRPHNHCPEESL
"""


# just a combination
SITES = """\
110817
PhosphoSitePlus(R) (PSP) was created by Cell Signaling Technology Inc. It is licensed under a Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported License. When using PSP data or analyses in printed publications or in online resources, the following acknowledgements must be included: (a) the words "PhosphoSitePlus(R), www.phosphosite.org" must be included at appropriate places in the text or webpage, and (b) the following citation must be included in the bibliography: "Hornbeck PV, Zhang B, Murray B, Kornhauser JM, Latham V, Skrzypek E PhosphoSitePlus, 2014: mutations, PTMs and recalibrations. Nucleic Acids Res. 2015 43:D512-20. PMID: 25514926."

GENE	PROTEIN	ACC_ID	HU_CHR_LOC	MOD_RSD	SITE_GRP_ID	ORGANISM	MW_kD	DOMAIN	SITE_+/-7_AA	LT_LIT	MS_LIT	MS_CST	CST_CAT#
CALCA	CALCA	P01258	11p15.2	T105-ga	27911933	human	15.47	Calc_CGRP_IAPP	QDFNKFHtFPQtAIG		1		
CALCA	CALCA	P01258	11p15.2	T109-ga	27911936	human	15.47	Calc_CGRP_IAPP	KFHtFPQtAIGVGAP		1		
"""


class TestImport(DatabaseTest):

    def test_glycosylation_import(self):
        protein = Protein(
            refseq='NM_001741',
            sequence='MGFQKFSPFLALSILVLLQAGSLHAAPFRSALESSPADPATLSEDEARLLLAALVQNYVQMKASELEQEQEREGSSLDSPRSKRCGNLSTCMLGTYTQDFNKFHTFPQTAIGVGAPGKKRDMSSDLERDHRPHVSMPQNAN*'
        )

        db.session.add(protein)

        with TemporaryDirectory() as dir_path:

            with gzip.open(dir_path + '/O-GalNAc_site_dataset.gz', 'wt') as f:
                f.write(SITES)

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
