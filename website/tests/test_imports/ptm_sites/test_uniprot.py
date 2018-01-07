from numpy import nan, isnan
from pandas import DataFrame
from pytest import warns

from database import db
from database_testing import DatabaseTest
from imports.sites.uniprot import OthersUniprotImporter
from imports.sites.uniprot import GlycosylationUniprotImporter
from miscellaneous import make_named_gz_file, make_named_temp_file
from models import Protein
from test_imports.ptm_sites.test_hprd import gene_from_isoforms
from test_imports.test_proteins import create_test_proteins


SEQUENCES = """\
>sp|P01889|1B07_HUMAN HLA class I histocompatibility antigen, B-7 alpha chain OS=Homo sapiens GN=HLA-B PE=1 SV=3
MLVMAPRTVLLLLSAALALTETWAGSHSMRYFYTSVSRPGRGEPRFISVGYVDDTQFVRF
DSDAASPREEPRAPWIEQEGPEYWDRNTQIYKAQAQTDRESLRNLRGYYNQSEAGSHTLQ
SMYGCDVGPDGRLLRGHDQYAYDGKDYIALNEDLRSWTAADTAAQITQRKWEAAREAEQR
RAYLEGECVEWLRRYLENGKDKLERADPPKTHVTHHPISDHEATLRCWALGFYPAEITLT
WQRDGEDQTQDTELVETRPAGDRTFQKWAAVVVPSGEEQRYTCHVQHEGLPKPLTLRWEP
SSQSTVPIVGIVAGLAVLAVVVIGAVVAAVMCRRKSSGGKGGSYSQAACSDSAQGSDVSL
TA
>sp|P01891|1A68_HUMAN HLA class I histocompatibility antigen, A-68 alpha chain OS=Homo sapiens GN=HLA-A PE=1 SV=4
MAVMAPRTLVLLLSGALALTQTWAGSHSMRYFYTSVSRPGRGEPRFIAVGYVDDTQFVRF
DSDAASQRMEPRAPWIEQEGPEYWDRNTRNVKAQSQTDRVDLGTLRGYYNQSEAGSHTIQ
MMYGCDVGSDGRFLRGYRQDAYDGKDYIALKEDLRSWTAADMAAQTTKHKWEAAHVAEQW
RAYLEGTCVEWLRRYLENGKETLQRTDAPKTHMTHHAVSDHEATLRCWALSFYPAEITLT
WQRDGEDQTQDTELVETRPAGDGTFQKWVAVVVPSGQEQRYTCHVQHEGLPKPLTLRWEP
SSQPTIPIVGIIAGLVLFGAVITGAVVAAVMWRRKSSDRKGGSYSQAASSDSAQGSDVSL
TACKV
>sp|Q2M3G0|ABCB5_HUMAN ATP-binding cassette sub-family B member 5 OS=Homo sapiens GN=ABCB5 PE=1 SV=4
MENSERAEEMQENYQRNGTAEEQPKLRKEAVGSIEIFRFADGLDITLMILGILASLVNGA
CLPLMPLVLGEMSDNLISGCLVQTNTTNYQNCTQSQEKLNEDMTLLTLYYVGIGVAALIF
GYIQISLWIITAARQTKRIRKQFFHSVLAQDIGWFDSCDIGELNTRMTDDIDKISDGIGD
KIALLFQNMSTFSIGLAVGLVKGWKLTLVTLSTSPLIMASAAACSRMVISLTSKELSAYS
KAGAVAEEVLSSIRTVIAFRAQEKELQRYTQNLKDAKDFGIKRTIASKVSLGAVYFFMNG
TYGLAFWYGTSLILNGEPGYTIGTVLAVFFSVIHSSYCIGAAVPHFETFAIARGAAFHIF
QVIDKKPSIDNFSTAGYKPESIEGTVEFKNVSFNYPSRPSIKILKGLNLRIKSGETVALV
GLNGSGKSTVVQLLQRLYDPDDGFIMVDENDIRALNVRHYRDHIGVVSQEPVLFGTTISN
NIKYGRDDVTDEEMERAAREANAYDFIMEFPNKFNTLVGEKGAQMSGGQKQRIAIARALV
RNPKILILDEATSALDSESKSAVQAALEKASKGRTTIVVAHRLSTIRSADLIVTLKDGML
AEKGAHAELMAKRGLYYSLVMSQDIKKADEQMESMTYSTERKTNSLPLHSVKSIKSDFID
KAEESTQSKEISLPEVSLLKILKLNKPEWPFVVLGTLASVLNGTVHPVFSIIFAKIITMF
GNNDKTTLKHDAEIYSMIFVILGVICFVSYFMQGLFYGRAGEILTMRLRHLAFKAMLYQD
IAWFDEKENSTGGLTTILAIDIAQIQGATGSRIGVLTQNATNMGLSVIISFIYGWEMTFL
ILSIAPVLAVTGMIETAAMTGFANKDKQELKHAGKIATEALENIRTIVSLTREKAFEQMY
EEMLQTQHRNTSKKAQIIGSCYAFSHAFIYFAYAAGFRFGAYLIQAGRMTPEGMFIVFTA
IAYGAMAIGETLVLAPEYSKAKSGAAHLFALLEKKPNIDSRSQEGKKPDTCEGNLEFREV
SFFYPCRPDVFILRGLSLSIERGKTVAFVGSSGCGKSTSVQLLQRLYDPVQGQVLFDGVD
AKELNVQWLRSQIAIVPQEPVLFNCSIAENIAYGDNSRVVPLDEIKEAANAANIHSFIEG
LPEKYNTQVGLKGAQLSGGQKQRLAIARALLQKPKILLLDEATSALDNDSEKVVQHALDK
ARTGRTCLVVTHRLSAIQNADLIVVLHNGKIKEQGTHQELLRNRDIYFKLVNAQSVQ
"""

GLYCOSYLATION_SITES = """\
primary_accession,sequence_accession,position,data,eco,source
"P01889","P01889-1","110"^^<http://www.w3.org/2001/XMLSchema#int>,"N-linked (GlcNAc...) asparagine","ECO_0000269",http://purl.uniprot.org/citations/19159218
"P01891","P01891-1","110"^^<http://www.w3.org/2001/XMLSchema#int>,"N-linked (GlcNAc...) asparagine","ECO_0000269",http://purl.uniprot.org/citations/19159218
"Q2M3G0","Q2M3G0-4","1188"^^<http://www.w3.org/2001/XMLSchema#int>,"N-linked (GlcNAc...) asparagine","ECO_0000255",
"""

SIMPLE_SITES = """\
primary_accession,sequence_accession,position,data,eco,source
"Q12797","Q12797-1","14"^^<http://www.w3.org/2001/XMLSchema#int>,"Phosphoserine","ECO_0000244",http://purl.uniprot.org/citations/24275569
"""

MAPPINGS = """\
P01889	RefSeq_NT	NM_005514.7
P01891	Gene_Name	HLA-A
Q2M3G0-4	RefSeq_NT	NM_001163941.1
Q2M3G0-1	RefSeq_NT	XM_011515367.2
Q2M3G0-1	RefSeq_NT	NM_178559.5
"""


SEQUENCES_SPLICE_TEST_CANONICAL = """\
>sp|Q12797|ASPH_HUMAN Aspartyl/asparaginyl beta-hydroxylase OS=Homo sapiens GN=ASPH PE=1 SV=3
MAQRKNAKSSGNSSSSGSGSGSTSAGSSSPGARRETKHGGHKNGRKGGLSGTSFFTWFMV
IALLGVWTSVAVVWFDLVDYEEVLGKLGIYDADGDGDFDVDDAKVLLGLKERSTSEPAVP
PEEAEPHTEPEEQVPVEAEPQNIEDEAKEQIQSLLHEMVHAEHVEGEDLQQEDGPTGEPQ
QEDDEFLMATDVDDRFETLEPEVSHEETEHSYHVEETVSQDCNQDMEEMMSEQENPDSSE
PVVEDERLHHDTDDVTYQVYEEQAVYEPLENEGIEITEVTAPPEDNPVEDSQVIVEEVSI
FPVEEQQEVPPETNRKTDDPEQKAKVKKKKPKLLNKFDKTIKAELDAAEKLRKRGKIEEA
VNAFKELVRKYPQSPRARYGKAQCEDDLAEKRRSNEVLRGAIETYQEVASLPDVPADLLK
LSLKRRSDRQQFLGHMRGSLLTLQRLVQLFPNDTSLKNDLGVGYLLIGDNDNAKKVYEEV
LSVTPNDGFAKVHYGFILKAQNKIAESIPYLKEGIESGDPGTDDGRFYFHLGDAMQRVGN
KEAYKWYELGHKRGHFASVWQRSLYNVNGLKAQPWWTPKETGYTELVKSLERNWKLIRDE
GLAVMDKAKGLFLPEDENLREKGDWSQFTLWQQGRRNENACKGAPKTCTLLEKFPETTGC
RRGQIKYSIMHPGTHVWPHTGPTNCRLRMHLGLVIPKEGCKIRCANETKTWEEGKVLIFD
DSFEHEVWQDASSFRLIFIVDVWHPELTPQQRRSLPAI
"""

SEQUENCES_SPLICE_TEST_SPLICE = """\
>sp|Q12797-3|ASPH_HUMAN Isoform 3 of Aspartyl/asparaginyl beta-hydroxylase OS=Homo sapiens GN=ASPH
MAEDKETKHGGHKNGRKGGLSGTSFFTWFMVIALLGVWTSVAVVWFDLVDYEEVLAKAKD
FRYNLSEVLQGKLGIYDADGDGDFDVDDAKVLLEGPSGVAKRKTKAKVKELTKEELKKEK
EKPESRKESKNEERKKGKKEDVRKDKKIADADLSRKESPKGKKDREKEKVDLEKSAKTKE
NRKKSTNMKDVSSKMASRDKDDRKESRSSTRYAHLTKGNTQKRNG
"""


SITES_SPLICE_TEST = """\
primary_accession,sequence_accession,position,data,eco,source
"Q12797","Q12797-1","706"^^<http://www.w3.org/2001/XMLSchema#int>,"N-linked (GlcNAc...) asparagine","ECO_0000255",
"Q12797","Q12797-1","452"^^<http://www.w3.org/2001/XMLSchema#int>,"N-linked (GlcNAc...) asparagine",,
"Q12797","Q12797-3","64"^^<http://www.w3.org/2001/XMLSchema#int>,"N-linked (GlcNAc...) asparagine",,
"""


MAPPINGS_SPLICE_TEST = """\
Q12797-1	RefSeq_NT	NM_004318.3
Q12797-3	RefSeq_NT	NM_020164.4
"""


DUAL_MAPPING = """\
P78423	RefSeq	NP_001291321.1
P78423	RefSeq_NT	NM_001304392.1
P78423	RefSeq	NP_002987.1
P78423	RefSeq_NT	NM_002996.4
"""


def make_test_shared_proteins():

    proteins = [
        Protein(refseq='NM_004318', sequence='MAQRKNAKSSGNSSSSGSGSGSTSAGSSSPGARRETKHGGHKNGRKGGLSGTSFFTWFMVIALLGVWTSVAVVWFDLVDYEEVLGKLGIYDADGDGDFDVDDAKVLLGLKERSTSEPAVPPEEAEPHTEPEEQVPVEAEPQNIEDEAKEQIQSLLHEMVHAEHVEGEDLQQEDGPTGEPQQEDDEFLMATDVDDRFETLEPEVSHEETEHSYHVEETVSQDCNQDMEEMMSEQENPDSSEPVVEDERLHHDTDDVTYQVYEEQAVYEPLENEGIEITEVTAPPEDNPVEDSQVIVEEVSIFPVEEQQEVPPETNRKTDDPEQKAKVKKKKPKLLNKFDKTIKAELDAAEKLRKRGKIEEAVNAFKELVRKYPQSPRARYGKAQCEDDLAEKRRSNEVLRGAIETYQEVASLPDVPADLLKLSLKRRSDRQQFLGHMRGSLLTLQRLVQLFPNDTSLKNDLGVGYLLIGDNDNAKKVYEEVLSVTPNDGFAKVHYGFILKAQNKIAESIPYLKEGIESGDPGTDDGRFYFHLGDAMQRVGNKEAYKWYELGHKRGHFASVWQRSLYNVNGLKAQPWWTPKETGYTELVKSLERNWKLIRDEGLAVMDKAKGLFLPEDENLREKGDWSQFTLWQQGRRNENACKGAPKTCTLLEKFPETTGCRRGQIKYSIMHPGTHVWPHTGPTNCRLRMHLGLVIPKEGCKIRCANETKTWEEGKVLIFDDSFEHEVWQDASSFRLIFIVDVWHPELTPQQRRSLPAI*'),
        Protein(refseq='NM_020164', sequence='MAEDKETKHGGHKNGRKGGLSGTSFFTWFMVIALLGVWTSVAVVWFDLVDYEEVLAKAKDFRYNLSEVLQGKLGIYDADGDGDFDVDDAKVLLEGPSGVAKRKTKAKVKELTKEELKKEKEKPESRKESKNEERKKGKKEDVRKDKKIADADLSRKESPKGKKDREKEKVDLEKSAKTKENRKKSTNMKDVSSKMASRDKDDRKESRSSTRYAHLTKGNTQKRNG*')
    ]

    db.session.add_all(proteins)

    db.session.commit()


test_data_with_splice_variants = (
    make_named_gz_file(SEQUENCES_SPLICE_TEST_CANONICAL),
    make_named_gz_file(SEQUENCES_SPLICE_TEST_SPLICE),
    make_named_gz_file(MAPPINGS_SPLICE_TEST)
)


def equal_or_both_nan(a, b):
    return a == b or (isnan(a) and isnan(b))


def verify_uniprot_importer_mappings(importer, cases):

    for site_data, (residue, ptm_type, kinases) in cases.items():
        inferred = importer.extract_site_mod_type(DataFrame({'data': [site_data]}))

        assert len(inferred) == 1

        i = inferred.iloc[0]

        assert equal_or_both_nan(i.residue, residue)
        assert i.mod_type == ptm_type
        assert equal_or_both_nan(i.kinases, kinases)


class TestImport(DatabaseTest):

    def test_glycosylation_import(self):
        # P01891 is not mappable to refseq, we should be warned about that
        proteins = create_test_proteins(['NM_001163941', 'NM_005514', 'NM_178559'])

        # sequence is needed for validation. Validation is tested on model level.
        sequences = {
            'NM_001163941': 'MENSERAEEMQENYQRNGTAEEQPKLRKEAVGSIEIFRFADGLDITLMILGILASLVNGACLPLMPLVLGEMSDNLISGCLVQTNTTNYQNCTQSQEKLNEDMTLLTLYYVGIGVAALIFGYIQISLWIITAARQTKRIRKQFFHSVLAQDIGWFDSCDIGELNTRMTDDIDKISDGIGDKIALLFQNMSTFSIGLAVGLVKGWKLTLVTLSTSPLIMASAAACSRMVISLTSKELSAYSKAGAVAEEVLSSIRTVIAFRAQEKELQRYTQNLKDAKDFGIKRTIASKVSLGAVYFFMNGTYGLAFWYGTSLILNGEPGYTIGTVLAVFFSVIHSSYCIGAAVPHFETFAIARGAAFHIFQVIDKKPSIDNFSTAGYKPESIEGTVEFKNVSFNYPSRPSIKILKGLNLRIKSGETVALVGLNGSGKSTVVQLLQRLYDPDDGFIMVDENDIRALNVRHYRDHIGVVSQEPVLFGTTISNNIKYGRDDVTDEEMERAAREANAYDFIMEFPNKFNTLVGEKGAQMSGGQKQRIAIARALVRNPKILILDEATSALDSESKSAVQAALEKASKGRTTIVVAHRLSTIRSADLIVTLKDGMLAEKGAHAELMAKRGLYYSLVMSQDIKKADEQMESMTYSTERKTNSLPLHSVKSIKSDFIDKAEESTQSKEISLPEVSLLKILKLNKPEWPFVVLGTLASVLNGTVHPVFSIIFAKIITMFGNNDKTTLKHDAEIYSMIFVILGVICFVSYFMQGLFYGRAGEILTMRLRHLAFKAMLYQDIAWFDEKENSTGGLTTILAIDIAQIQGATGSRIGVLTQNATNMGLSVIISFIYGWEMTFLILSIAPVLAVTGMIETAAMTGFANKDKQELKHAGKIATEALENIRTIVSLTREKAFEQMYEEMLQTQHRNTSKKAQIIGSCYAFSHAFIYFAYAAGFRFGAYLIQAGRMTPEGMFIVFTAIAYGAMAIGETLVLAPEYSKAKSGAAHLFALLEKKPNIDSRSQEGKKPDTCEGNLEFREVSFFYPCRPDVFILRGLSLSIERGKTVAFVGSSGCGKSTSVQLLQRLYDPVQGQVLFDGVDAKELNVQWLRSQIAIVPQEPVLFNCSIAENIAYGDNSRVVPLDEIKEAANAANIHSFIEGLPEKYNTQVGLKGAQLSGGQKQRLAIARALLQKPKILLLDEATSALDNDSEKVVQHALDKARTGRTCLVVTHRLSAIQNADLIVVLHNGKIKEQGTHQELLRNRDIYFKLVNAQSVQ*',
            'NM_178559': 'MVDENDIRALNVRHYRDHIGVVSQEPVLFGTTISNNIKYGRDDVTDEEMERAAREANAYDFIMEFPNKFNTLVGEKGAQMSGGQKQRIAIARALVRNPKILILDEATSALDSESKSAVQAALEKASKGRTTIVVAHRLSTIRSADLIVTLKDGMLAEKGAHAELMAKRGLYYSLVMSQDIKKADEQMESMTYSTERKTNSLPLHSVKSIKSDFIDKAEESTQSKEISLPEVSLLKILKLNKPEWPFVVLGTLASVLNGTVHPVFSIIFAKIITMFGNNDKTTLKHDAEIYSMIFVILGVICFVSYFMQGLFYGRAGEILTMRLRHLAFKAMLYQDIAWFDEKENSTGGLTTILAIDIAQIQGATGSRIGVLTQNATNMGLSVIISFIYGWEMTFLILSIAPVLAVTGMIETAAMTGFANKDKQELKHAGKIATEALENIRTIVSLTREKAFEQMYEEMLQTQHRNTSKKAQIIGSCYAFSHAFIYFAYAAGFRFGAYLIQAGRMTPEGMFIVFTAIAYGAMAIGETLVLAPEYSKAKSGAAHLFALLEKKPNIDSRSQEGKKPDTCEGNLEFREVSFFYPCRPDVFILRGLSLSIERGKTVAFVGSSGCGKSTSVQLLQRLYDPVQGQVLFDGVDAKELNVQWLRSQIAIVPQEPVLFNCSIAENIAYGDNSRVVPLDEIKEAANAANIHSFIEGLPEKYNTQVGLKGAQLSGGQKQRLAIARALLQKPKILLLDEATSALDNDSEKVVQHALDKARTGRTCLVVTHRLSAIQNADLIVVLHNGKIKEQGTHQELLRNRDIYFKLVNAQSVQ*',
            'NM_005514': 'MLVMAPRTVLLLLSAALALTETWAGSHSMRYFYTSVSRPGRGEPRFISVGYVDDTQFVRFDSDAASPREEPRAPWIEQEGPEYWDRNTQIYKAQAQTDRESLRNLRGYYNQSEAGSHTLQSMYGCDVGPDGRLLRGHDQYAYDGKDYIALNEDLRSWTAADTAAQITQRKWEAAREAEQRRAYLEGECVEWLRRYLENGKDKLERADPPKTHVTHHPISDHEATLRCWALGFYPAEITLTWQRDGEDQTQDTELVETRPAGDRTFQKWAAVVVPSGEEQRYTCHVQHEGLPKPLTLRWEPSSQSTVPIVGIVAGLAVLAVVVIGAVVAAVMCRRKSSGGKGGSYSQAACSDSAQGSDVSLTA'
        }

        for isoform, sequence in sequences.items():
            proteins[isoform].sequence = sequence

        db.session.add_all(proteins.values())

        # Add gene to test cross-isoform mapping
        abcb5 = gene_from_isoforms(proteins, ['NM_001163941', 'NM_178559'])
        db.session.add(abcb5)

        importer = GlycosylationUniprotImporter(
            make_named_gz_file(SEQUENCES),
            make_named_gz_file(''),
            make_named_gz_file(MAPPINGS)
        )

        assert len(importer.mappings) == 3

        sites = importer.load_sites(path=make_named_temp_file(GLYCOSYLATION_SITES))

        # should have 2 pre-defined sites (3 but one without refseq equivalent) and one mapped (isoform NM_178559)
        assert len(sites) == 2 + 1

        sites_by_isoform = {site.protein.refseq: site for site in sites}

        assert sites_by_isoform['NM_001163941'].residue == sites_by_isoform['NM_178559'].residue == 'N'

    def test_splice_variants_handling(self):
        """Verify import of sites from a multi-splice variants entry (here: Q12797)"""

        make_test_shared_proteins()

        importer = GlycosylationUniprotImporter(*test_data_with_splice_variants)

        sites = importer.load_sites(path=make_named_temp_file(SITES_SPLICE_TEST))

        assert len(sites) == 3

    def test_glycans_mapping(self):
        cases = {
            'O-linked (GlcNAc) tyrosine; by Photorhabdus PAU_02230': ('Y', 'glycosylation', ['Photorhabdus PAU_02230']),
            'O-linked (Hex) serine': ('S', 'glycosylation', nan),
            'O-linked (GalNAc...) serine; in variant S-874': ('S', 'glycosylation', nan),
            'S-linked (Gal...) cysteine': ('C', 'glycosylation', nan),
            'N-linked (GlcNAc...) asparagine': ('N', 'glycosylation', nan),
            'N-linked (GlcNAc...)': (nan, 'glycosylation', nan),
            'N-linked (Glc) (glycation) lysine': ('K', 'glycation', nan)
        }
        importer = GlycosylationUniprotImporter(*test_data_with_splice_variants)

        verify_uniprot_importer_mappings(importer, cases)

    def test_others_mapping(self):
        # list of important cases:
        # cat data/sites/UniProt/other_sites.csv | cut -d ',' -f 4 | sort | uniq
        # full list of keywords:
        # http://www.uniprot.org/docs/ptmlist

        cases = {
            'Phosphohistidine': ('H', 'phosphorylation', nan),
            'Phosphoserine': ('S', 'phosphorylation', nan),
            'Phosphoserine; alternate': ('S', 'phosphorylation', nan),
            'Phosphoserine; by AURKB': ('S', 'phosphorylation', ['AURKB']),
            'Phosphoserine; alternate; by AURKB': ('S', 'phosphorylation', ['AURKB']),
            'Phosphoserine; by AMPK and RPS6KA1': ('S', 'phosphorylation', ['AMPK', 'RPS6KA1']),
            'Phosphoserine; by CaMK2; in vitro': ('S', 'phosphorylation', ['CaMK2']),
            'Phosphotyrosine; by ZAP70': ('Y', 'phosphorylation', ['ZAP70']),
            'Phosphothreonine; in form 5-P': ('T', 'phosphorylation', nan),
            'Phosphothreonine; by MAPK1 AND MAPK3': ('T', 'phosphorylation', ['MAPK1', 'MAPK3']),
            'Phosphothreonine; by MAPK1 or MAPK3': ('T', 'phosphorylation', ['MAPK1', 'MAPK3']),
            'Pros-phosphohistidine': ('H', 'phosphorylation', nan),
            'N6-acetyllysine': ('K', 'acetylation', nan),
            'N-acetylalanine; in Beta-crystallin B3': ('A', 'acetylation', nan),
            'N-acetylaspartate': ('D', 'acetylation', nan),
            'N-acetylcysteine; in intermediate form': ('C', 'acetylation', nan),
            'N-acetylglutamate': ('E', 'acetylation', nan),
            'N-acetylglycine; in Tyrosine--tRNA ligase': ('G', 'acetylation', nan),
            'N-acetylmethionine; in peptidyl-prolyl cis-trans isomerase FKBP4; alternate': ('M', 'acetylation', nan),
            'N-acetylproline': ('P', 'acetylation', nan),
            'N-acetylvaline': ('V', 'acetylation', nan),
            'O-acetylserine; by Yersinia yopJ; alternate': ('S', 'acetylation', ['Yersinia yopJ']),
            'N2-acetylarginine': ('R', 'acetylation', nan),
            'Symmetric dimethylarginine; alternate; by PRMT5': ('R', 'methylation', ['PRMT5']),
            'Omega-N-methylated arginine; by CARM1; in vitro': ('R', 'methylation', ['CARM1']),
            'N-methylglycine; alternate': ('G', 'methylation', nan),
            'N6-methyllysine; by EHMT1 and EHMT2': ('K', 'methylation', ['EHMT1', 'EHMT2']),
            'Dimethylated arginine; in A2780 ovarian carcinoma cell line': ('R', 'methylation', nan)
        }

        importer = OthersUniprotImporter(*test_data_with_splice_variants)

        verify_uniprot_importer_mappings(importer, cases)

    def test_others_import(self):

        make_test_shared_proteins()

        importer = OthersUniprotImporter(*test_data_with_splice_variants)

        sites = importer.load_sites(path=make_named_temp_file(SIMPLE_SITES))

        assert len(sites) == 1

    def test_missing_sequence(self):
        """Sometimes (though rarely) there is no sequence for given accession.

        This happens when UniProt fasta files are not in sync with SPRQL API.
        """

        site_with_missing_sequence = (
            'primary_accession,sequence_accession,position,data,eco,source\n'
            '"B2RDS2","B2RDS2-1","79^","N-linked (GlcNAc...) asparagine","ECO_0000256",'
        )

        importer = GlycosylationUniprotImporter(
            make_named_gz_file(''),
            make_named_gz_file(''),
            make_named_gz_file('B2RDS2	RefSeq_NT	NM_004823.1')
        )

        with warns(UserWarning, match='No sequence for .* found!'):
            importer.load_sites(make_named_temp_file(site_with_missing_sequence))

    def test_refseq_mapping(self):

        importer = GlycosylationUniprotImporter(
            make_named_gz_file(''),
            make_named_gz_file(''),
            make_named_gz_file(DUAL_MAPPING),
        )

        sites = DataFrame(data={'sequence_accession': ['P78423-1']})

        sites_with_refseq = importer.add_nm_refseq_identifiers(sites)

        assert len(sites_with_refseq) == 2
