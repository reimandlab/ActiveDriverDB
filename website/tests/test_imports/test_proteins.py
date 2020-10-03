import gzip
from typing import Dict

from imports.protein_data import get_proteins
from imports.protein_data import clean_from_wrong_proteins
from imports.protein_data import proteins_and_genes
from imports.protein_data import select_preferred_isoform
from imports.protein_data import sequences as sequences_importer
from imports.protein_data import disorder as disorder_importer
from imports.protein_data import conservation as conservation_importer
from imports.protein_data import full_gene_names as full_gene_names_importer
from imports.protein_data import protein_summaries
from database_testing import DatabaseTest
from miscellaneous import make_named_temp_file
from database import db
from models import Protein, ProteinReferences, UniprotEntry
from models import Gene


# head data/protein_data.tsv -n 5
protein_data = """\
bin	name	chrom	strand	txStart	txEnd	cdsStart	cdsEnd	exonCount	exonStarts	exonEnds	score	name2	cdsStartStat	cdsEndStat	exonFrames
732	NM_002749	chr17	+	19281773	19286857	19282213	19286544	7	19281773,19282208,19283094,19283920,19285093,19286125,19286390,	19281943,19282445,19283260,19284999,19285779,19286259,19286857,	0	MAPK7	cmpl	cmpl	-1,0,1,2,1,0,2,
1757	NM_021806	chrX	-	153734489	153744566	153735141	153744096	9	153734489,153735533,153735736,153736141,153736619,153736804,153740180,153741146,153744083,	153735237,153735660,153735821,153736192,153736678,153736928,153740204,153741260,153744566,	0FAM3A	cmpl	cmpl	0,2,1,1,2,1,1,1,0,
1768	NM_001204289	chr1	-	155158299	155162706	155158610	155162634	7	155158299,155159700,155159930,155160197,155160483,155161973,155162576,	155158685,155159850,155160052,155160334,155160530,155162101,155162706,	0	MUC1	cmpl	cmpl	0,0,1,2,0,1,0,
758	NM_000600	chr7	+	22766765	22771621	22766881	22771192	5	22766765,22767062,22768311,22769132,22771024,	22766900,22767253,22768425,22769279,22771621,	0	IL6	cmpl	cmpl	0,1,0,0,0,\
"""

# head data/protein_data.tsv -n 6 | tail -n 2
update_data = """\
bin	name	chrom	strand	txStart	txEnd	cdsStart	cdsEnd	exonCount	exonStarts	exonEnds	score	name2	cdsStartStat	cdsEndStat	exonFrames
758	NM_000600	chr7	+	22766765	22771621	22766881	22771192	5	22766765,22767062,22768311,22769132,22771024,	22766900,22767253,22768425,22769279,22771621,	0	IL6	cmpl	cmpl	0,1,0,0,0,
1364	NM_182962	chr11	+	102188180	102210135	102195240	102207833	10	102188180,102192567,102195191,102196196,102198782,102199627,102201729,102206696,102207490,102207639,	102188302,102192631,102196093,102196296,102198861,102199676,102201972,102206951,102207532,102210135,	0	BIRC3	cmpl	cmpl	-1,-1,0,1,2,0,1,1,1,1,\
"""

# head data/all_RefGene_proteins.fa -n 6
fasta_sequences = """\
>NM_002749
MAEPLKEEDGEDGSAEPPGPVKAEPAHTAASVAAKNLALLKARSFDVTFDVGDEYEIIETIGNGAYGVVSSARRRLTGQQVAIKKIPNAFDVVTNAKRTLRELKILKHFKHDNIIAIKDILRPTVPYGEFKSVYVVLDLMESDLHQIIHSSQPLTLEHVRYFLYQLLRGLKYMHSAQVIHRDLKPSNLLVNENCELKIGDFGMARGLCTSPAEHQYFMTEYVATRWYRAPELMLSLHEYTQAIDLWSVGCIFGEMLARRQLFPGKNYVHQLQLIMMVLGTPSPAVIQAVGAERVRAYIQSLPPRQPVPWETVYPGADRQALSLLGRMLRFEPSARISAAAALRHPFLAKYHDPDDEPDCAPPFDFAFDREALTRERIKEAIVAEIEDFHARREGIRQQIRFQPSLQPVASEPGCPDVEMPSPWAPSGDCAMESPPPAPPPCPGPAPDTIDLTLQPPPPVSEPAPPKKDGAISDNTKAALKAALLKSLRSRLRDGPSAPLEAPEPRKPVTAQERQREREEKRRRRQERAKEREKRRQERERKERGAGASGGPSTDPLAGLVLSDNDRSLLERWTRMARPAAPALTSVPAPAPAPTPTPTPVQPTSPPPGPVAQPTGPQPQSAGSTSGPVPQPACPPPGPAPHPTGPPGPIPVPAPPQIATSTSLLAAQSLVPPPGLPGSSTPGVLPYFPPGLPPPDAGGAPQSSMSESPDVNLVTQQLSKSQVEDPLPPVFSGTPKGSGAGYGVGFDLEEFLNQSFDMGVADGPQDGQADSASLSASLLADWLEGHGMNPADIESLQREIQMDSPMLLADLPDLQDP*
>NM_021806
MRLAGPLRIVVLVVSVGVTWIVVSILLGGPGSGFPRIQQLFTSPESSVTAAPRARKYKCGLPQPCPEEHLAFRVVSGAANVIGPKICLEDKMLMSSVKDNVGRGLNIALVNGVSGELIEARAFDMWAGDVNDLLKFIRPLHEGTLVFVASYDDPATKMNEETRKLFSELGSRNAKELAFRDSWVFVGAKGVQNKSPFEQHVKNSKHSNKYEGWPEALEMEGCIPRRSTAS*
>NM_001204289
MTPGTQSPFFLLLLLTVLTATTAPKPATVVTGSGHASSTPGGEKETSATQRSSVPSSTEKNAIYKQGGFLGLSNIKFRPGSVVVQLTLAFREGTINVHDVETQFNQYKTEAASRYNLTISDVSVSDVPFPFSAQSGAGVPGWGIALLVLVCVLVALAIVYLIALAVCQCRRKNYGQLDIFPARDTYHPMSEYPTYHTHGRYVPPSSTDRSPYEKVSAGNGGSSLSYTNPAVAATSANL*\
"""

sequences_for_proteins = {
    'NM_002749': 'MAEPLKEEDGEDGSAEPPGPVKAEPAHTAASVAAKNLALLKARSFDVTFDVGDEYEIIETIGNGAYGVVSSARRRLTGQQVAIKKIPNAFDVVTNAKRTLRELKILKHFKHDNIIAIKDILRPTVPYGEFKSVYVVLDLMESDLHQIIHSSQPLTLEHVRYFLYQLLRGLKYMHSAQVIHRDLKPSNLLVNENCELKIGDFGMARGLCTSPAEHQYFMTEYVATRWYRAPELMLSLHEYTQAIDLWSVGCIFGEMLARRQLFPGKNYVHQLQLIMMVLGTPSPAVIQAVGAERVRAYIQSLPPRQPVPWETVYPGADRQALSLLGRMLRFEPSARISAAAALRHPFLAKYHDPDDEPDCAPPFDFAFDREALTRERIKEAIVAEIEDFHARREGIRQQIRFQPSLQPVASEPGCPDVEMPSPWAPSGDCAMESPPPAPPPCPGPAPDTIDLTLQPPPPVSEPAPPKKDGAISDNTKAALKAALLKSLRSRLRDGPSAPLEAPEPRKPVTAQERQREREEKRRRRQERAKEREKRRQERERKERGAGASGGPSTDPLAGLVLSDNDRSLLERWTRMARPAAPALTSVPAPAPAPTPTPTPVQPTSPPPGPVAQPTGPQPQSAGSTSGPVPQPACPPPGPAPHPTGPPGPIPVPAPPQIATSTSLLAAQSLVPPPGLPGSSTPGVLPYFPPGLPPPDAGGAPQSSMSESPDVNLVTQQLSKSQVEDPLPPVFSGTPKGSGAGYGVGFDLEEFLNQSFDMGVADGPQDGQADSASLSASLLADWLEGHGMNPADIESLQREIQMDSPMLLADLPDLQDP*',
    'NM_000600': 'MNSFSTSAFGPVAFSLGLLLVLPAAFPAPVPPGEDSKDVAAPHRQPLTSSERIDKQIRYILDGISALRKETCNKSNMCESSKEALAENNLNLPKMAEKDGCFQSGFNEETCLVKIITGLLEFEVYLEYLQNRFESSEEQARAVQMSTKVLIQFLQKKAKNLDAITTPDPTTNASLLTKLQAQNQWLQDMTTHLILRSFKEFLQSSLRALRQM'
}

# excerpt from data/all_RefGene_disorder.fa
disorder_data = """\
>NM_002749
111111111111111111111111111111110000000000000000000000000000
000000000000000000000000000000000000000000000000000000000000
>NM_000600
111111111111010000000000000000111111111111111000000000000000
00000000000000000000000000000000
"""

# selection of data/refseq_summary.tsv.gz, trimmed for test purposes
summaries_data = """\
#mrnaAcc	completeness	summary
NM_153081	Complete3End	
NM_010410	Complete3End	This gene encodes a hypothalamic neuropeptide precursor [...]
NR_132735	Complete3End	
NM_182751	Complete3End	The protein encoded by this gene is one of the highly [...]
NR_029833	Unknown	microRNAs (miRNAs) are short (20-24 nt) non-coding RNAs that are [...]
"""

# one gene in db, one gene not in db, one gene without full name
full_gene_names = """\
#tax_id	GeneID	Symbol	LocusTag	Synonyms	dbXrefs	chromosome	map_location	description	type_of_gene	Symbol_from_nomenclature_authority	Full_name_from_nomenclature_authority	Nomenclature_status	Other_designations	Modification_date	Feature_type
9606	7157	TP53	-	BCC7|LFS1|P53|TRP53	MIM:191170|HGNC:HGNC:11998|Ensembl:ENSG00000141510|Vega:OTTHUMG00000162125	17	17p13.1	tumor protein p53	protein-coding	TP53	tumor protein p53	O	cellular tumor antigen p53|antigen NY-CO-13|mutant tumor protein 53|p53 tumor suppressor|phosphoprotein p53|transformation-related protein 53|tumor protein 53|tumor supressor p53	20170710	-
9606	1	A1BG	-	A1B|ABG|GAB|HYST2477	MIM:138670|HGNC:HGNC:5|Ensembl:ENSG00000121410|Vega:OTTHUMG00000183507	19	19q13.43	alpha-1-B glycoprotein	protein-coding	A1BG	alpha-1-B glycoprotein	O	alpha-1B-glycoprotein|HEL-S-163pA|epididymis secretory sperm binding protein Li 163pA	20170709	-
9606	628	BEVI	-	-	MIM:109180	6	-	baboon M7 virus integration site	unknown	-	-	-	Baboon M7 virus replication	20170408	-
"""


# Generated with:
"""
test_data = genes_data.loc[[('chr17', 'NM_002749'), ('chr7', 'NM_000600')]].reset_index()
test_data.exonStarts = test_data.exonStarts.apply(lambda x: ','.join(map(str, x)))
test_data.exonEnds = test_data.exonEnds.apply(lambda x: ','.join(map(str, x)))
test_data = test_data.drop('bin', axis='columns')
test_data.to_csv('test_data.tsv', sep='\t', header=False)
# and manually swap order of name/chrom
"""
coordinates_data = """\
0	NM_002749	chr17	+	19281773	19286857	19282213	19286544	7	19281773,19282208,19283094,19283920,19285093,19286125,19286390	19281943,19282445,19283260,19284999,19285779,19286259,19286857	0	MAPK7	cmpl	cmpl	-1,0,1,2,1,0,2,
1	NM_000600	chr7	+	22766760	22771621	22766881	22771192	522766760,22767062,22768311,22769132,22771024	22766900,22767253,22768425,22769279,22771621	0	IL6	cmpl	cmpl	0,1,0,0,0,
"""


def create_test_proteins(refseqs) -> Dict[str, Protein]:
    # reset cache
    proteins = get_proteins(reload_cache=True)

    for refseq in refseqs:
        proteins[refseq] = Protein(refseq=refseq)

    return proteins


class TestImport(DatabaseTest):

    def test_proteins_and_genes(self):

        create_test_proteins([])

        filename = make_named_temp_file(protein_data)

        with self.app.app_context():
            new_proteins = proteins_and_genes.load(path=filename)

        assert len(new_proteins) == 4
        db.session.add_all(new_proteins)

        p = Protein.query.filter_by(refseq='NM_002749').one()
        g = Gene.query.filter_by(name='MAPK7').one()

        assert p.gene == g
        assert p.tx_start == 19281773
        assert p.tx_end == 19286857
        assert p.cds_start == 19282213
        assert p.cds_end == 19286544

        # test genes
        genes = Gene.query.all()
        assert len(genes) == 4

        # test strands:
        assert g.strand is True
        assert Gene.query.filter_by(name='MUC1').one().strand is False

        second_filename = make_named_temp_file(update_data)

        with self.app.app_context():
            new_proteins = proteins_and_genes.load(path=second_filename)

        assert len(new_proteins) == 1

        protein = list(new_proteins)[0]
        assert protein.refseq == 'NM_182962'

    def test_sequences(self):

        proteins = create_test_proteins(['NM_002749', 'NM_021806', 'NM_001204289'])

        filename = make_named_temp_file(fasta_sequences)

        with self.app.app_context():
            sequences_importer.load(filename)

        protein = proteins['NM_021806']
        assert protein.sequence == 'MRLAGPLRIVVLVVSVGVTWIVVSILLGGPGSGFPRIQQLFTSPESSVTAAPRARKYKCGLPQPCPEEHLAFRVVSGAANVIGPKICLEDKMLMSSVKDNVGRGLNIALVNGVSGELIEARAFDMWAGDVNDLLKFIRPLHEGTLVFVASYDDPATKMNEETRKLFSELGSRNAKELAFRDSWVFVGAKGVQNKSPFEQHVKNSKHSNKYEGWPEALEMEGCIPRRSTAS*'
        assert protein.length == len('MRLAGPLRIVVLVVSVGVTWIVVSILLGGPGSGFPRIQQLFTSPESSVTAAPRARKYKCGLPQPCPEEHLAFRVVSGAANVIGPKICLEDKMLMSSVKDNVGRGLNIALVNGVSGELIEARAFDMWAGDVNDLLKFIRPLHEGTLVFVASYDDPATKMNEETRKLFSELGSRNAKELAFRDSWVFVGAKGVQNKSPFEQHVKNSKHSNKYEGWPEALEMEGCIPRRSTAS')

    def test_disorder(self):

        proteins = create_test_proteins(['NM_002749', 'NM_000600'])
        for refseq, protein in proteins.items():
            protein.sequence = sequences_for_proteins[refseq]

        filename = make_named_temp_file(disorder_data)

        with self.app.app_context():
            disorder_importer.load(filename)

        assert proteins['NM_002749'].disorder_map == '111111111111111111111111111111110000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        assert proteins['NM_000600'].disorder_map == '11111111111101000000000000000011111111111111100000000000000000000000000000000000000000000000'

    def test_conservation(self):

        proteins = create_test_proteins(['NM_002749', 'NM_000600'])
        proteins['NM_002749'].gene = Gene(name='MAPK7', chrom='17')
        proteins['NM_000600'].gene = Gene(name='IL6', chrom='7')

        for refseq, protein in proteins.items():
            protein.sequence = sequences_for_proteins[refseq]

        # Generated with:
        """
            import pyBigWig
            test_data = test_data.loc[('chr17', 'NM_002749')].iloc[0]
            full_bw = pyBigWig.open('data/hg19.100way.phyloP100way.bw')
            test_bw = pyBigWig.open('chr17_NM_002749.test_data.bw', 'w')
            needed_chrom_length = max(max(test_data.exonStarts), max(test_data.exonEnds))
            test_bw.addHeader([('chr17', needed_chrom_length)])
            coordinates = sorted(zip(test_data.exonStarts, test_data.exonEnds), key=lambda x: x[0])
            for start, end in zip(test_data.exonStarts, test_data.exonEnds):
                values = full_bw.values('chr17', start, end)
                for i, value in enumerate(values):
                    test_bw.addEntries(['chr17'], starts=[start + i], ends=[start + i + 1], values=[value])
            test_bw.close()
        """
        conservation_big_wig = 'tests/test_imports/chr17_NM_002749.test_data.bw'

        gene_coordinates = make_named_temp_file(coordinates_data)
        conservation_importer.load(conservation_big_wig, gene_coordinates)

        # Protein.query.filter_by(refseq='NM_002749').one().conservation
        assert proteins['NM_002749'].conservation == '3.47;1.67;2.95;1.23;.9;1.64;4.08;1.72;1.25;1.15;2.26;1.69;1.03;1.05;2.39;1.52;2.88;.5;2.28;-.09;2.24;1.32;-.06;.59;1.2;-.13;.37;.76;.04;1.26;-.2;1.84;.97;2.95;5.67;3.98;2.91;4.5;2.33;3.17;4.66;3.73;4.24;4.01;2.49;4.35;5.29;2.95;4.67;5.66;5.36;5.25;4.23;4.87;5.31;5.18;3.52;4.53;5.59;3.55;5.05;6.65;2.01;5.75;5.06;4.88;5.9;4.9;5.63;3.32;3.52;5.09;4.04;4.24;2.24;1.84;2.13;6.12;6.54;2.75;6.08;5.79;5.7;8.26;6.81;5.82;3.83;4.47;3.08;5.11;5;3.4;2.52;4.67;3.97;3.58;4.87;3.72;5.33;4.48;3.92;6.79;3.7;7.52;5.46;4.05;3.07;4.02;5.47;5.31;5.12;7.11;6.59;6.09;5.37;4.73;5.6;6.3;6.52;5.96;3.32;2.84;4.06;.53;3.5;3.79;3.11;1.81;4.51;4.81;3.35;4.29;5.34;5.31;4.63;6.41;2.39;6.46;3.16;8.2;6.23;2.67;6.63;2.39;4.07;5;3.49;4.71;4.16;3.27;.7;6.43;1.1;3.25;2.31;1.57;6.39;5.62;2.68;4.33;6.16;6;3.28;6.16;6.66;3.66;3.77;4.11;6.52;3.69;6.55;5.97;5.28;5.9;3.63;6.16;5.36;5.92;4.24;6.23;4.27;7.07;5.64;6.62;5.32;1.79;6.59;3.26;4.38;3.92;6.2;3.59;5.22;5.76;6.77;4.58;7.52;4.24;3.91;5.75;5.28;6.51;7.43;5.49;2.98;5.48;2.01;2.62;2.19;1.95;1.01;2.03;5.55;1.47;2.2;2.38;5.52;5.93;3.39;6.62;5.51;6.67;5.67;3.9;6.03;8.99;6.67;4.17;4.7;4.01;6.27;3.7;5.06;3.66;2.06;2.64;3.76;2.56;5.94;3.82;2.89;4.05;5.17;6.75;3.05;8.99;4.25;5.57;6.66;6.22;6.06;3.65;4.13;6.66;8.76;2.77;2.34;1.65;1.84;3.91;3.38;5.3;3.49;6.22;3.21;3.91;5.43;2.8;4.28;6.44;3.25;3.89;2.56;5.75;4.58;1.02;5.09;3.53;5.75;5;3.97;3.24;2.08;.17;3.51;2.96;1.66;2.99;3.71;4.75;3.78;5.8;3.71;5.3;4.16;3.18;4.66;3.56;6.62;4.69;2.96;4.27;3.1;3.49;2.38;2.54;3.18;4.54;5.17;3.34;.46;4.2;3.77;2.53;1.27;3.6;4.46;.83;1.58;4.57;2.92;2.17;2.81;3.17;1.48;1.13;8.45;2.85;1.15;4.09;5.67;3.85;.82;1.15;3.3;3.95;.21;4.67;1.19;2.83;5.43;3.54;.76;5.35;3.81;3.85;3.23;2.46;5.65;5.76;3.97;6.32;3.35;2.86;5.95;6.63;4.5;2.89;5.45;3.95;4.59;4.34;5.09;4.99;5.24;4.02;4.91;5.83;1.59;2.45;1.71;2.51;2.87;2.93;6;3.07;4.58;5.09;5.26;4.44;4.06;3.28;2.1;6.69;4.55;2.58;5.57;4.79;3.75;.58;1.99;2.45;4.16;3.64;1.55;3.8;2.09;3.71;4.36;2.27;4.31;4.26;3.43;1.01;.44;1.57;1.7;2.68;1.46;1.5;1.7;.7;.92;1.94;1.42;2.39;.76;3.24;3.14;1.01;2.85;1.17;1.48;1.22;.67;.8;.75;3.02;1.12;1.34;4.82;3.73;1.26;.92;-.86;1.13;.65;1.18;.06;-.67;.8;.2;.41;.35;.05;.69;1.11;1.09;.06;1.29;2.34;.9;-.06;.36;1.24;-.18;.06;-.14;.87;.86;2.37;1.38;.52;1.97;.97;4.2;1.48;4.38;5.02;3.81;4.14;3.29;4.98;4.21;4.73;5.01;2.84;4.03;4.01;4.89;4.64;2.37;1.66;2.52;5.89;3.6;1.53;1.1;2.19;1.25;1;2.33;2.53;1.89;2.01;1;.84;-.21;.93;2.4;2.06;1.91;4.48;.3;3.03;2.21;2.16;4.76;4.08;4.42;4.07;5.72;3.13;3.52;2.69;5.1;3.98;3.99;5.24;5.81;2.02;1.75;3.18;2.96;4.36;4.26;3.2;3.71;1.85;4.88;2.93;4.94;4.22;2.17;1.67;2.44;4.68;1.22;3.37;1.68;1.73;2.69;1.65;.75;-.94;1.27;.11;-.79;3;1.26;.57;1.71;.45;2.93;1.48;1.67;2.62;3.54;.95;3.03;2.33;2.5;3.92;2.41;3.3;2.08;2.16;.87;1.26;3.18;3.02;4.04;1.48;.78;4.1;2.06;.59;1.89;.25;.44;-.23;-.57;-.45;.33;-.12;.22;-1.71;.1;.63;.58;.04;-.21;.5;-2.18;.06;.06;-.46;-.39;-.23;.26;.36;.42;.86;1.85;.56;.27;-.51;.65;.42;-.35;.43;.93;.05;-.66;.28;.09;.41;-.05;.46;.51;.02;.67;.11;-.55;.27;.09;.77;-.18;.11;2.34;.99;.1;.78;.52;1.23;.3;.04;.31;-.42;.13;.78;1.01;-.48;.98;.14;.65;.25;.97;-.67;.8;.49;1.15;.15;-1.05;.52;1.43;.04;.68;-.14;-.15;.24;.73;1.71;.89;-.05;.68;.53;.1;.52;.81;1.56;.28;.07;2.18;.55;1.24;2.33;.78;-.04;.77;-.09;.4;.61;.96;1.59;1.57;1.71;1.52;1.41;1.11;1.48;.52;1.61;.76;2.41;.05;.73;-.38;.4;1.78;.95;.46;2.29;1.05;1.94;1.74;.88;1.32;1.97;1.66;1.64;1.17;2.12;2.38;2.63;2.64;1.63;2.49;3.23;1.49;4.21;5.62;5.72;5.3;.78;3.01;4.23;3.16;3.53;5.02;3.73;4.38;4.53;4.4;6.09;6.37;5.1;5.65;4.64;5.8;4.94;5.24;4.63;6.08;4.74;4.27;4.1;5.34;5.96;3.64;2.03;3.29;5.31;2.6;2.34;2.25;4.26;2.1;2.08;2.48;.6;1.53;.31;1.96;4.53;3.8;3.27;.67;5.5;2.33;4.89;2.31;3.4;4.37;3.71;4.24;2.89;3.27;2.97;5.14;7.61;2.14;5.73;3.45;4.27;3.13;5.77;4.91;2.21;2.5;4.74;3.57;4.6;3.43;3.41;6.01;3.21;5.22;3.11;6.33;4.8;4.29;5.23;3.28;6.47;2.48;6.01;3.17;5.92;1.38;1.79;2.96;2.67;2.21;2.67;1.89'

        # no data for this one, lets see if the pipeline handles such cases well
        assert proteins['NM_000600'].conservation is None

        db.session.add_all(proteins.values())
        db.session.commit()

        assert Protein.query.filter_by(refseq='NM_000600').one().conservation == ''

    def test_select_preferred_isoform(self):
        # if is_first_isoform, simulate the case when there is a first isoform,
        # otherwise simulate the case with picking a non-isoform specific one
        for is_first_isoform in [True, False]:

            proteins_data = [
                ('NM_001', 'MA', False),
                ('NM_002', 'MAA', True),
                ('NM_003', 'MAAA', True),   # we want this one:
                                            # canonical according to uniprot, then longest, then oldest in refseq
                ('NM_004', 'MAAA', True),
                ('NM_005', 'MAAAA', False)
            ]

            preferred_refseq = 'NM_003'

            gene = Gene(name='Gene X')
            for refseq, seq, is_uniprot_canonical in proteins_data:
                protein = Protein(refseq=refseq, sequence=seq, gene=gene)
                if is_uniprot_canonical:
                    protein_references = ProteinReferences(uniprot_entries=[
                        UniprotEntry(isoform=1 if is_first_isoform else None, reviewed=True)
                    ])
                    protein.external_references = protein_references

            db.session.add(gene)

            isoform = select_preferred_isoform(gene)
            assert isoform
            print(is_first_isoform)
            assert isoform.refseq == preferred_refseq

    def test_protein_summaries(self):

        proteins = create_test_proteins(['NM_010410', 'NM_182751'])

        filename = make_named_temp_file(summaries_data, mode='wt', opener=gzip.open)

        with self.app.app_context():

            protein_summaries.load(path=filename)

        assert proteins['NM_010410'].summary == 'This gene encodes a hypothalamic neuropeptide precursor [...]'
        assert proteins['NM_182751'].summary == 'The protein encoded by this gene is one of the highly [...]'

    def test_gene_full_name(self):

        gene = Gene(name='TP53', entrez_id=7157)
        db.session.add(gene)

        filename = make_named_temp_file(full_gene_names, mode='wt', opener=gzip.open)

        full_gene_names_importer.load(filename)

        assert gene.full_name == 'tumor protein p53'

    def test_remove_unwanted_proteins(self):

        sequences = {
            'NM_1': 'MAKS*',   # all right
            'NM_2': 'MKFR',    # lack of stop codon
            'NM_3': 'MK*A',    # premature stop codon
        }

        proteins = create_test_proteins(['NM_1', 'NM_2', 'NM_3'])

        gene = Gene(
            isoforms=list(proteins.values()),
            preferred_isoform=proteins['NM_3']
        )

        db.session.add_all(proteins.values())
        db.session.add(gene)

        for fake_refseq, protein in proteins.items():
            protein.sequence = sequences[fake_refseq]

        clean_from_wrong_proteins.load()

        # NM_2 and NM_3 should be removed, NM_1 should still be there
        assert len(proteins) == 1
        assert 'NM_1' in proteins

        for refseq in ['NM_2', 'NM_3']:
            assert refseq not in proteins

        # NM_1 should become a preferred isoform of gene (in place of NM_3)
        assert gene.preferred_refseq == 'NM_1'
