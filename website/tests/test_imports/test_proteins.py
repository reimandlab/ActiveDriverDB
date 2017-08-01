from imports.protein_data import get_proteins
from imports.protein_data import proteins_and_genes
from imports.protein_data import select_preferred_isoform
from imports.protein_data import sequences as load_sequences
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


class TestImport(DatabaseTest):

    def test_proteins_and_genes(self):

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
        db.session.add_all(new_proteins)

        protein = list(new_proteins)[0]
        assert protein.refseq == 'NM_182962'

    def test_sequences(self):

        refseqs = ('NM_002749', 'NM_021806', 'NM_001204289')

        proteins = get_proteins(reload_cache=True)

        for refseq in refseqs:
            proteins[refseq] = Protein(refseq=refseq)

        filename = make_named_temp_file(fasta_sequences)

        with self.app.app_context():
            load_sequences(filename)

        protein = proteins['NM_021806']
        assert protein.sequence == 'MRLAGPLRIVVLVVSVGVTWIVVSILLGGPGSGFPRIQQLFTSPESSVTAAPRARKYKCGLPQPCPEEHLAFRVVSGAANVIGPKICLEDKMLMSSVKDNVGRGLNIALVNGVSGELIEARAFDMWAGDVNDLLKFIRPLHEGTLVFVASYDDPATKMNEETRKLFSELGSRNAKELAFRDSWVFVGAKGVQNKSPFEQHVKNSKHSNKYEGWPEALEMEGCIPRRSTAS*'
        assert protein.length == len('MRLAGPLRIVVLVVSVGVTWIVVSILLGGPGSGFPRIQQLFTSPESSVTAAPRARKYKCGLPQPCPEEHLAFRVVSGAANVIGPKICLEDKMLMSSVKDNVGRGLNIALVNGVSGELIEARAFDMWAGDVNDLLKFIRPLHEGTLVFVASYDDPATKMNEETRKLFSELGSRNAKELAFRDSWVFVGAKGVQNKSPFEQHVKNSKHSNKYEGWPEALEMEGCIPRRSTAS')

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
