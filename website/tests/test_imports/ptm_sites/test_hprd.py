from warnings import warn

from pytest import warns

from database import db
from database_testing import DatabaseTest
from imports.sites.hprd import HPRDImporter
from miscellaneous import make_named_temp_file
from models import Gene, Protein
from test_imports.test_proteins import create_test_proteins

SEQUENCES = """\
>00001|00001_1|NP_000680.2|Aldehyde dehydrogenase 1
MSSSGTPDLPVLLTDLKIQYTKIFINNEWHDSVSGKKFPVFNPATEEELCQVEEGDKEDVDKAVKAARQAFQIGSPWRTMDASERGRLLYKLADLIERDRLLLATMESMNGGKLYSNAYLNDLAGCIKTLRYCAGWADKIQGRTIPIDGNFFTYTRHEPIGVCGQIIPWNFPLVMLIWKIGPALSCGNTVVVKPAEQTPLTALHVASLIKEAGFPPGVVNIVPGYGPTAGAAISSHMDIDKVAFTGSTEVGKLIKEAAGKSNLKRVTLELGGKSPCIVLADADLDNAVEFAHHGVFYHQGQCCIAASRIFVEESIYDEFVRRSVERAKKYILGNPLTPGVTQGPQIDKEQYDKILDLIESGKKEGAKLECGGGPWGNKGYFVQPTVFSNVTDEMRIAKEEIFGPVQQIMKFKSLDDVIKRANNTFYGLSAGVFTKDIDKAITISSALQAGTVWVNCYGVVSAQCPFGGFKMSGNGRELGEYGFHEYTEVKTVTVKISQKNS
>00002|00002_1|NP_001988.1|FAU
MQLFVRAQELHTFEVTGQETVAQIKAHVASLEGIAPEDQVVLLAGAPLEDEATLGQCGVEALTTLEVAGRMLGGKVHGSLARAGKVRGQTPKVAKQEKKKKKTGRAKRRMQYNRRFVNVVPTFGKKKGPNANS
>00003|00003_1|NP_000681.2|Aldehyde dehydrogenase 2
MLRAAARFGPRLGRRLLSAAATQAVPAPNQQPEVFCNQIFINNEWHDAVSRKTFPTVNPSTGEVICQVAEGDKEDVDKAVKAARAAFQLGSPWRRMDASHRGRLLNRLADLIERDRTYLAALETLDNGKPYVISYLVDLDMVLKCLRYYAGWADKYHGKTIPIDGDFFSYTRHEPVGVCGQIIPWNFPLLMQAWKLGPALATGNVVVMKVA
EQTPLTALYVANLIKEAGFPPGVVNIVPGFGPTAGAAIASHEDVDKVAFTGSTEIGRVIQVAAGSSNLKRVTLELGGKSPNIIMSDADMDWAVEQAHFALFFNQGQCCCAGSRTFVQEDIYDEFVERSVARAKSRVVGNPFDSKTEQGPQVDETQFKKILGYINTGKQEGAKLLCGGGIAADRGYFIQPTVFGDVQDGMTIAKEEIFGPVM
QILKFKTIEEVVGRANNSTYGLAAAVFTKDLDKANYLSQALQAGTVWVNCYDVFGAQSPFGGYKMSGSGRELGEYGLQAYTEVKTVTVKVPQKNS
"""

SITES = """\
00001	ALDH1A1	00001_1	NP_000680.2	2	S	-	-	Acetylation	in vitro	6427007
00002	FAU	00002_1	NP_001988.1	125	K	-	-	Acetylation	in vivo	19608861
00003	ALDH2	00003_1	NP_000681.2	480	S	-	-	Phosphorylation	in vivo	18452278
"""

MAPPINGS = """\
00001	ALDH1A1	NM_000689.3	NP_000680.2	216	100640	P00352	Aldehyde dehydrogenase 1
00002	FAU	NM_001997.3	NP_001988.1	2197	134690	P35544	FAU
00003	ALDH2	NM_000690.2	NP_000681.2	217	100650	P05091	Aldehyde dehydrogenase 2
"""


def gene_from_isoforms(all_proteins, chosen_isoforms):
    """Just for testing: in normal settings the bi-directional initialization is performed required"""
    isoforms = [protein for refseq, protein in all_proteins.items() if refseq in chosen_isoforms]
    gene = Gene(isoforms=isoforms)
    for isoform in isoforms:
        isoform.gene = gene
    return gene


class TestImport(DatabaseTest):

    def test_import(self):
        proteins = create_test_proteins(['NM_000689', 'NM_001997', 'NM_000690', 'NM_001204889'])

        # Sequence is needed for validation. Validation is tested on model level.
        sequences = {
            'NM_000689': 'MSSSGTPDLPVLLTDLKIQYTKIFINNEWHDSVSGKKFPVFNPATEEELCQVEEGDKEDVDKAVKAARQAFQIGSPWRTMDASERGRLLYKLADLIERDRLLLATMESMNGGKLYSNAYLNDLAGCIKTLRYCAGWADKIQGRTIPIDGNFFTYTRHEPIGVCGQIIPWNFPLVMLIWKIGPALSCGNTVVVKPAEQTPLTALHVASLIKEAGFPPGVVNIVPGYGPTAGAAISSHMDIDKVAFTGSTEVGKLIKEAAGKSNLKRVTLELGGKSPCIVLADADLDNAVEFAHHGVFYHQGQCCIAASRIFVEESIYDEFVRRSVERAKKYILGNPLTPGVTQGPQIDKEQYDKILDLIESGKKEGAKLECGGGPWGNKGYFVQPTVFSNVTDEMRIAKEEIFGPVQQIMKFKSLDDVIKRANNTFYGLSAGVFTKDIDKAITISSALQAGTVWVNCYGVVSAQCPFGGFKMSGNGRELGEYGFHEYTEVKTVTVKISQKNS*',
            'NM_001997': 'MQLFVRAQELHTFEVTGQETVAQIKAHVASLEGIAPEDQVVLLAGAPLEDEATLGQCGVEALTTLEVAGRMLGGKVHGSLARAGKVRGQTPKVAKQEKKKKKTGRAKRRMQYNRRFVNVVPTFGKKKGPNANS*',
            'NM_000690': 'MLRAAARFGPRLGRRLLSAAATQAVPAPNQQPEVFCNQIFINNEWHDAVSRKTFPTVNPSTGEVICQVAEGDKEDVDKAVKAARAAFQLGSPWRRMDASHRGRLLNRLADLIERDRTYLAALETLDNGKPYVISYLVDLDMVLKCLRYYAGWADKYHGKTIPIDGDFFSYTRHEPVGVCGQIIPWNFPLLMQAWKLGPALATGNVVVMKVAEQTPLTALYVANLIKEAGFPPGVVNIVPGFGPTAGAAIASHEDVDKVAFTGSTEIGRVIQVAAGSSNLKRVTLELGGKSPNIIMSDADMDWAVEQAHFALFFNQGQCCCAGSRTFVQEDIYDEFVERSVARAKSRVVGNPFDSKTEQGPQVDETQFKKILGYINTGKQEGAKLLCGGGIAADRGYFIQPTVFGDVQDGMTIAKEEIFGPVMQILKFKTIEEVVGRANNSTYGLAAAVFTKDLDKANYLSQALQAGTVWVNCYDVFGAQSPFGGYKMSGSGRELGEYGLQAYTEVKTVTVKVPQKNS*',
            'NM_001204889': 'MLRAAARFGPRLGRRLLSAAATQAVPAPNQQPEVFCNQIFINNEWHDAVSRKTFPTVNPSTGEVICQVAEGDKALETLDNGKPYVISYLVDLDMVLKCLRYYAGWADKYHGKTIPIDGDFFSYTRHEPVGVCGQIIPWNFPLLMQAWKLGPALATGNVVVMKVAEQTPLTALYVANLIKEAGFPPGVVNIVPGFGPTAGAAIASHEDVDKVAFTGSTEIGRVIQVAAGSSNLKRVTLELGGKSPNIIMSDADMDWAVEQAHFALFFNQGQCCCAGSRTFVQEDIYDEFVERSVARAKSRVVGNPFDSKTEQGPQVDETQFKKILGYINTGKQEGAKLLCGGGIAADRGYFIQPTVFGDVQDGMTIAKEEIFGPVMQILKFKTIEEVVGRANNSTYGLAAAVFTKDLDKANYLSQALQAGTVWVNCYDVFGAQSPFGGYKMSGSGRELGEYGLQAYTEVKTVTVKVPQKNS*'
        }

        for isoform, sequence in sequences.items():
            proteins[isoform].sequence = sequence

        db.session.add_all(proteins.values())

        # Add gene to test cross-isoform mapping
        aldh2 = gene_from_isoforms(proteins, ['NM_000690', 'NM_001204889'])
        db.session.add(aldh2)

        importer = HPRDImporter(make_named_temp_file(SEQUENCES), make_named_temp_file(MAPPINGS), dir_path='')

        assert len(importer.mappings) == 3

        with warns(None) as warnings:
            sites = importer.load_sites(path=make_named_temp_file(SITES))

        if warnings.list:
            for warning in warnings.list:
                warn(warning.message)
            raise AssertionError

        # should have 3 pre-defined sites and one mapped (isoform NM_001204889)
        assert len(sites) == 3 + 1

        sites_by_isoform = {site.protein.refseq: site for site in sites}

        assert sites_by_isoform['NM_001204889'].residue == sites_by_isoform['NM_000690'].residue == 'S'
        assert sites_by_isoform['NM_000689'].position == 2

    def test_exceptions(self):

        sites_data = (
            # this odd case is real:
            '02098	NONO	02098_1	NP_031389.3	0	Y	-	-	Acetylation	in vivo	19608861'
            # there are 9 such cases in HPRD at the time of this test creation
        )
        mappings = '02098	NONO	NM_007363.4	NP_031389.3	4841	300084	Q15233,B7Z4C2	Non pou domain containing octamer binding protein'
        sequences = (
            '>02098|02098_1|NP_031389.3|Non pou domain containing octamer binding protein\n'
            'MQSNKTFNLEKQNHTPRKHHQHHHQQQHHQQQQQQPPPPPIPANGQQASSQNEGLTIDLKNFRKPGEKTFTQRSRLFVG'
            # the main part of the sequence was cut out as it is not needed
            # but this is the important bit: it has 'Y' at the end:
            'GTLGLTPPTTERFGQAATMEGIGAIGGTPPAFNRAAPGAEFAPNKRRRY'
            # so having 1-based positioning system, after a naive conversion to 0-based:
            # site.pos = -1; furthermore, sequence[site.pos] == 'Y' (!); this is probably
            # why the pos = '0' had been saved in HPRD in the first place.
        )
        protein = Protein(
            refseq='NM_007363',
            sequence='MQSNKTFNLEKQNHTPRKHHQHHHQQQHHQQQQQQPPPPPIPANGQQASSQNEGLTIDLKNFRKPGEKTFTQRSRLFVG'
                     'GTLGLTPPTTERFGQAATMEGIGAIGGTPPAFNRAAPGAEFAPNKRRRY'
        )
        db.session.add(protein)

        importer = HPRDImporter(make_named_temp_file(sequences), make_named_temp_file(mappings), dir_path='')

        # without a fix, it should warn and reject the faulty site
        with warns(UserWarning, match='The site: 02098_1: 0Y is outside of the protein sequence'):
            sites = importer.load_sites(path=make_named_temp_file(sites_data), pos_zero_means_last_aa=False)

        assert len(sites) == 0

        # and it should work when a workaround is applied
        with warns(None) as warnings:
            sites = importer.load_sites(path=make_named_temp_file(sites_data), pos_zero_means_last_aa=True)

        assert not warnings.list
        assert len(sites) == 1

        site = sites[0]

        assert site.position == 128
        assert site.residue == 'Y'


"""
Additional caveats:
Sometimes HPRD positions are 1-based:

>04715|04715_2|NP_001030178.1|Ribosomal protein L17
MVRYSLDPENPTKSCKSRGSNLRVHFKNTRETAQAIKGMHIRKATKYLKDVT...
   ||
   45 (both are 1-based)

04715	RPL17	04715_2	NP_001030178.1	4	Y	-	-	Phosphorylation	in vivo	18691976
04715	RPL17	04715_2	NP_001030178.1	5	S	-	-	Phosphorylation	in vivo	18691976,19007248


Sometimes are 0-based:

>01812|01812_1|NP_003225.2|Transferrin receptor
MMDQARSAFSNLFGGEPLSYTRFSLARQVDGDNSHVEMKLAVDEEENADNNTK...
                  |              |
                  19 (0-based)  34 (1-based)

01812	TFRC	01812_1	NP_003225.2	19	Y	-	-	Phosphorylation	in vivo	17016520
01812	TFRC	01812_1	NP_003225.2	34	S	-	-	Phosphorylation	in vivo	20068231
"""
