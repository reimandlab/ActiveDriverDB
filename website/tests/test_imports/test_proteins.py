import gzip

from imports.protein_data import get_proteins
from imports.protein_data import clean_from_wrong_proteins
from imports.protein_data import proteins_and_genes
from imports.protein_data import select_preferred_isoform
from imports.protein_data import sequences as load_sequences
from imports.protein_data import disorder as load_disorder
from imports.protein_data import full_gene_names as load_full_gene_names
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


def create_test_proteins(refseqs):
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
            new_proteins = proteins_and_genes(path=filename)

        assert len(new_proteins) == 4
        db.session.add_all(new_proteins)

        p = Protein.query.filter_by(refseq='NM_002749').one()
        g = Gene.query.filter_by(name='MAPK7').one()

        assert p.gene == g
        assert p.tx_start == 19281773
        assert p.tx_end == 19286857
        assert p.cds_start == 19282213
        assert p.cds_end == 19286544

        second_filename = make_named_temp_file(update_data)

        with self.app.app_context():
            new_proteins = proteins_and_genes(path=second_filename)

        assert len(new_proteins) == 1

        protein = list(new_proteins)[0]
        assert protein.refseq == 'NM_182962'

    def test_sequences(self):

        proteins = create_test_proteins(['NM_002749', 'NM_021806', 'NM_001204289'])

        filename = make_named_temp_file(fasta_sequences)

        with self.app.app_context():
            load_sequences(filename)

        protein = proteins['NM_021806']
        assert protein.sequence == 'MRLAGPLRIVVLVVSVGVTWIVVSILLGGPGSGFPRIQQLFTSPESSVTAAPRARKYKCGLPQPCPEEHLAFRVVSGAANVIGPKICLEDKMLMSSVKDNVGRGLNIALVNGVSGELIEARAFDMWAGDVNDLLKFIRPLHEGTLVFVASYDDPATKMNEETRKLFSELGSRNAKELAFRDSWVFVGAKGVQNKSPFEQHVKNSKHSNKYEGWPEALEMEGCIPRRSTAS*'
        assert protein.length == len('MRLAGPLRIVVLVVSVGVTWIVVSILLGGPGSGFPRIQQLFTSPESSVTAAPRARKYKCGLPQPCPEEHLAFRVVSGAANVIGPKICLEDKMLMSSVKDNVGRGLNIALVNGVSGELIEARAFDMWAGDVNDLLKFIRPLHEGTLVFVASYDDPATKMNEETRKLFSELGSRNAKELAFRDSWVFVGAKGVQNKSPFEQHVKNSKHSNKYEGWPEALEMEGCIPRRSTAS')

    def test_disorder(self):

        proteins = create_test_proteins(['NM_002749', 'NM_000600'])

        filename = make_named_temp_file(disorder_data)

        with self.app.app_context():
            load_disorder(filename)

        assert proteins['NM_002749'].disorder_map == '111111111111111111111111111111110000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        assert proteins['NM_000600'].disorder_map == '11111111111101000000000000000011111111111111100000000000000000000000000000000000000000000000'

    def test_select_preferred_isoform(self):
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
                protein_references = ProteinReferences(uniprot_entries=[UniprotEntry(isoform=1, reviewed=True)])
                protein.external_references = protein_references

        db.session.add(gene)

        isoform = select_preferred_isoform(gene)
        assert isoform
        assert isoform.refseq == preferred_refseq

    def test_protein_summaries(self):

        proteins = create_test_proteins(['NM_010410', 'NM_182751'])

        filename = make_named_temp_file(summaries_data, mode='wt', opener=gzip.open)

        with self.app.app_context():

            protein_summaries(path=filename)

        assert proteins['NM_010410'].summary == 'This gene encodes a hypothalamic neuropeptide precursor [...]'
        assert proteins['NM_182751'].summary == 'The protein encoded by this gene is one of the highly [...]'

    def test_gene_full_name(self):

        gene = Gene(name='TP53', entrez_id=7157)
        db.session.add(gene)

        filename = make_named_temp_file(full_gene_names, mode='wt', opener=gzip.open)

        load_full_gene_names(filename)

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

        clean_from_wrong_proteins()

        # NM_2 and NM_3 should be removed, NM_1 should still be there
        assert len(proteins) == 1
        assert 'NM_1' in proteins

        for refseq in ['NM_2', 'NM_3']:
            assert refseq not in proteins

        # NM_1 should become a preferred isoform of gene (in place of NM_3)
        assert gene.preferred_refseq == 'NM_1'
