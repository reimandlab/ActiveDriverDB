import gzip
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Type

from database import db
from database_testing import DatabaseTest
from imports.sites.psp import PhosphoSitePlusImporter
from miscellaneous import make_named_gz_file, TestCaseData, abstract_property
from models import Protein


class PSPCaseData(TestCaseData):

    @abstract_property
    def mappings(self): pass

    @abstract_property
    def canonical(self): pass

    @abstract_property
    def alternative(self): pass

    @abstract_property
    def sites(self): pass

    @abstract_property
    def kinases(self): pass


class SimpleCase(PSPCaseData):

    mappings = """\
    P01258	RefSeq_NT	NM_001741.2
    P01258	RefSeq_NT	NM_001033952.2
    """

    canonical = """\
    >sp|P01258|CALC_HUMAN Calcitonin OS=Homo sapiens GN=CALCA PE=1 SV=2
    MGFQKFSPFLALSILVLLQAGSLHAAPFRSALESSPADPATLSEDEARLLLAALVQNYVQ
    MKASELEQEQEREGSSLDSPRSKRCGNLSTCMLGTYTQDFNKFHTFPQTAIGVGAPGKKR
    DMSSDLERDHRPHVSMPQNAN
    """

    alternative = """\
    >sp|P01258-2|CALC_HUMAN Isoform 2 of Calcitonin OS=Homo sapiens GN=CALCA
    MGFQKFSPFLALSILVLLQAGSLHAAPFRSALESSPADPATLSEDEARLLLAALVQNYVQ
    MKASELEQEQEREGSSLDSPRSKRCGNLSTCMLGTYTQDFNKFHTFPQTAIGVGAPGKKR
    DMSSDLERDHRPHNHCPEESL
    """

    sites = """\
    110817
    PhosphoSitePlus(R) (PSP) was created by Cell Signaling Technology Inc. It is licensed under a Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported License. When using PSP data or analyses in printed publications or in online resources, the following acknowledgements must be included: (a) the words "PhosphoSitePlus(R), www.phosphosite.org" must be included at appropriate places in the text or webpage, and (b) the following citation must be included in the bibliography: "Hornbeck PV, Zhang B, Murray B, Kornhauser JM, Latham V, Skrzypek E PhosphoSitePlus, 2014: mutations, PTMs and recalibrations. Nucleic Acids Res. 2015 43:D512-20. PMID: 25514926."

    GENE	PROTEIN	ACC_ID	HU_CHR_LOC	MOD_RSD	SITE_GRP_ID	ORGANISM	MW_kD	DOMAIN	SITE_+/-7_AA	LT_LIT	MS_LIT	MS_CST	CST_CAT#
    CALCA	CALCA	P01258	11p15.2	T105-ga	27911933	human	15.47	Calc_CGRP_IAPP	QDFNKFHtFPQtAIG		1		
    CALCA	CALCA	P01258	11p15.2	T109-ga	27911936	human	15.47	Calc_CGRP_IAPP	KFHtFPQtAIGVGAP		1		
    """

    kinases = """\
    110817
    Data extracted from PhosphoSitePlus(R), created by Cell Signaling Technology Inc. PhosphoSitePlus is licensed under a Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported License. Attribution must be given in written, oral and digital presentations to PhosphoSitePlus, www.phosphosite.org. Written documents should additionally cite Hornbeck PV, Kornhauser JM, Tkachev S, Zhang B, Skrzypek E, Murray B, Latham V, Sullivan M (2012) PhosphoSitePlus: a comprehensive resource for investigating the structure and function of experimentally determined post-translational modifications in man and mouse. Nucleic Acids Res. 40, D261�70.; www.phosphosite.org.

    GENE	KINASE	KIN_ACC_ID	KIN_ORGANISM	SUBSTRATE	SUB_GENE_ID	SUB_ACC_ID	SUB_GENE	SUB_ORGANISM	SUB_MOD_RSD	SITE_GRP_ID	SITE_+/-7_AA	DOMAIN	IN_VIVO_RXN	IN_VITRO_RXN	CST_CAT#
    """


class EdgeSitesCase(SimpleCase):

    mappings = """\
    Q15847	RefSeq_NT	NM_006829.2
    """

    canonical = """\
    >sp|Q15847|ADIRF_HUMAN Adipogenesis regulatory factor OS=Homo sapiens GN=ADIRF PE=1 SV=1
    MASKGLQDLKQQVEGTAQEAVSAAGAAAQQVVDQATEAGQKAMDQLAKTTQETIDKTANQASDTFSGIGKKFGLLK
    """

    alternative = ''

    # note: the real data would have no empty 'LT_LIT' column
    sites = """\
    110817
    PhosphoSitePlus(R) (PSP) was created by Cell Signaling Technology Inc. It is licensed under a Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported License. When using PSP data or analyses in printed publications or in online resources, the following acknowledgements must be included: (a) the words "PhosphoSitePlus(R), www.phosphosite.org" must be included at appropriate places in the text or webpage, and (b) the following citation must be included in the bibliography: "Hornbeck PV, Zhang B, Murray B, Kornhauser JM, Latham V, Skrzypek E PhosphoSitePlus, 2014: mutations, PTMs and recalibrations. Nucleic Acids Res. 2015 43:D512-20. PMID: 25514926."

    GENE	PROTEIN	ACC_ID	HU_CHR_LOC	MOD_RSD	SITE_GRP_ID	ORGANISM	MW_kD	DOMAIN	SITE_+/-7_AA	LT_LIT	MS_LIT	MS_CST	CST_CAT#
    ADIRF	ADIRF	Q15847	10q23.2	S3-p	50772639	human	7.85		_____MAsKGLQDLK	1	2		
    ADIRF	ADIRF	Q15847	10q23.2	K70-ac	466659	human	7.85		DtFsGIGkkFGLLK_	1		75	
    """


class WithKinases(PSPCaseData):

    mappings = """\
    Q03135-1	RefSeq_NT	NM_001753.4
    """

    canonical = """\
    >sp|Q03135|CAV1_HUMAN Caveolin-1 OS=Homo sapiens GN=CAV1 PE=1 SV=4
    MSGGKYVDSEGHLYTVPIREQGNIYKPNNKAMADELSEKQVYDAHTKEIDLVNRDPKHLN
    DDVVKIDFEDVIAEPEGTHSFDGIWKASFTTFTVTKYWFYRLLSALFGIPMALIWGIYFA
    ILSFLHIWAVVPCIKSFLIEIQCISRVYSIYVHTVCDPLFEAVGKIFSNVRINLQKEI
    """

    alternative = """\
    >sp|Q03135-2|CAV1_HUMAN Isoform 2 of Caveolin-1 OS=Homo sapiens GN=CAV1
    MADELSEKQVYDAHTKEIDLVNRDPKHLNDDVVKIDFEDVIAEPEGTHSFDGIWKASFTT
    FTVTKYWFYRLLSALFGIPMALIWGIYFAILSFLHIWAVVPCIKSFLIEIQCISRVYSIY
    VHTVCDPLFEAVGKIFSNVRINLQKEI
    """

    kinases = """\
    110817
    Data extracted from PhosphoSitePlus(R), created by Cell Signaling Technology Inc. PhosphoSitePlus is licensed under a Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported License. Attribution must be given in written, oral and digital presentations to PhosphoSitePlus, www.phosphosite.org. Written documents should additionally cite Hornbeck PV, Kornhauser JM, Tkachev S, Zhang B, Skrzypek E, Murray B, Latham V, Sullivan M (2012) PhosphoSitePlus: a comprehensive resource for investigating the structure and function of experimentally determined post-translational modifications in man and mouse. Nucleic Acids Res. 40, D261�70.; www.phosphosite.org.

    GENE	KINASE	KIN_ACC_ID	KIN_ORGANISM	SUBSTRATE	SUB_GENE_ID	SUB_ACC_ID	SUB_GENE	SUB_ORGANISM	SUB_MOD_RSD	SITE_GRP_ID	SITE_+/-7_AA	DOMAIN	IN_VIVO_RXN	IN_VITRO_RXN	CST_CAT#
    SRC	Src	P12931	human	caveolin-1	857	Q03135	CAV1	human	Y14	448422	VDsEGHLytVPIREQ		X	X	3251
    ABL1	Abl	P00519	human	caveolin-1	857	Q03135	CAV1	human	Y14	448422	VDsEGHLytVPIREQ		 	X	3251
    FYN	Fyn	P06241	human	caveolin-1	857	Q03135	CAV1	human	Y14	448422	VDsEGHLytVPIREQ		X	X	3251
    """

    sites = """\
    110817
    PhosphoSitePlus(R) (PSP) was created by Cell Signaling Technology Inc. It is licensed under a Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported License. When using PSP data or analyses in printed publications or in online resources, the following acknowledgements must be included: (a) the words "PhosphoSitePlus(R), www.phosphosite.org" must be included at appropriate places in the text or webpage, and (b) the following citation must be included in the bibliography: "Hornbeck PV, Zhang B, Murray B, Kornhauser JM, Latham V, Skrzypek E PhosphoSitePlus, 2014: mutations, PTMs and recalibrations. Nucleic Acids Res. 2015 43:D512-20. PMID: 25514926."

    GENE	PROTEIN	ACC_ID	HU_CHR_LOC	MOD_RSD	SITE_GRP_ID	ORGANISM	MW_kD	DOMAIN	SITE_+/-7_AA	LT_LIT	MS_LIT	MS_CST	CST_CAT#
    CAV1	caveolin-1	Q03135	7q31.2	Y14-p	448422	human	20.47		VDsEGHLytVPIREQ	21	28	768	3251
    """


@contextmanager
def initialized_importer(test_data: Type[PSPCaseData], dataset):
    with TemporaryDirectory() as dir_path:
        dir_path = Path(dir_path)

        with gzip.open(dir_path / f'{dataset}_site_dataset.gz', 'wt') as f:
            f.write(test_data.sites)

        with gzip.open(dir_path / 'Kinase_Substrate_Dataset.gz', 'wt') as f:
            f.write(test_data.kinases)

        importer = PhosphoSitePlusImporter(
            make_named_gz_file(test_data.canonical),
            make_named_gz_file(test_data.alternative),
            make_named_gz_file(test_data.mappings),
            dir_path=dir_path
        )

        yield importer


class TestImport(DatabaseTest):

    def test_import(self):
        protein = Protein(
            refseq='NM_001741',
            sequence='MGFQKFSPFLALSILVLLQAGSLHAAPFRSALESSPADPATLSEDEARLLLAALVQNYVQMKASELEQEQEREGSSLDSPRSKRCGNLSTCMLGTYTQDFNKFHTFPQTAIGVGAPGKKRDMSSDLERDHRPHVSMPQNAN*'
        )
        db.session.add(protein)

        with initialized_importer(SimpleCase, 'O-GalNAc') as importer:

            sites = importer.load_sites(site_datasets=['O-GalNAc'])

            assert len(sites) == 2

            sites_by_pos = {site.position: site for site in sites}

            assert sites_by_pos[105].residue == sites_by_pos[109].residue == 'T'
            assert sites_by_pos[105].type == {'glycosylation'}

    def test_edge_cases(self):

        protein = Protein(
            refseq='NM_006829',
            sequence='MASKGLQDLKQQVEGTAQEAVSAAGAAAQQVVDQATEAGQKAMDQLAKTTQETIDKTANQASDTFSGIGKKFGLLK*'
        )

        db.session.add(protein)

        with initialized_importer(EdgeSitesCase, 'My_test') as importer:

            importer.site_datasets['My_test'] = 'mixed_type'

            sites = importer.load_sites(site_datasets=['My_test'])

            assert len(sites) == 2

            sites_by_pos = {site.position: site for site in sites}

            assert sites_by_pos[3].residue == 'S'
            assert sites_by_pos[70].residue == 'K'

    def test_kinases(self):

        protein = Protein(
            refseq='NM_001753',
            sequence='MSGGKYVDSEGHLYTVPIREQGNIYKPNNKAMADELSEKQVYDAHTKEIDLVNRDPKHLNDDVVKIDFEDVIAEPEGTHSFDGIWKASFTTFTVTKYWFYRLLSALFGIPMALIWGIYFAILSFLHIWAVVPCIKSFLIEIQCISRVYSIYVHTVCDPLFEAVGKIFSNVRINLQKEI*'
        )

        db.session.add(protein)

        with initialized_importer(WithKinases, 'Phosphorylation') as importer:

            sites = importer.load_sites(site_datasets=['Phosphorylation'])

            assert len(sites) == 1

            site = sites[0]
            assert {kinase.name for kinase in site.kinases} == {'Src', 'Abl', 'Fyn'}
