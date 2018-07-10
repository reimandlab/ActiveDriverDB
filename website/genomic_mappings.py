from typing import List

from berkley_db import BerkleyHashSetWithCache


class GenomicMappings(BerkleyHashSetWithCache):

    def add_genomic_mut(self, chrom, dna_pos, dna_ref, dna_alt, aa_mut, strand='+', exon='EX1', is_ptm=False):
        """Add a genomic mutation mapping to provided 'mut' aminoacid mutation.

        This is a testing convenience function. Please refrain from using
        it for full-database imports as it *may* be hugely inefficient.
        """
        snv = make_snv_key(chrom, dna_pos, dna_ref, dna_alt)
        csv = encode_csv(
            strand, aa_mut.ref, aa_mut.alt, cdna_pos_from_aa(aa_mut.position),
            exon, aa_mut.protein.id, is_ptm
        )

        self.add(snv, csv)

    def get_genomic_muts(self, chrom, dna_pos, dna_ref, dna_alt) -> List[dict]:
        """Returns aminoacid mutations meeting provided criteria.

        There may be several mutations with the same genomic coordinates and alleles,
        as there are many splicing isoforms produced from a single gene.

        Stop codon mutations are not considered.

        Args:
            chrom: chromosome number or identifier, without 'chr' prefix
            dna_pos: genomic position
            dna_ref: reference allele
            dna_alt: alternative allele

        Returns:
            list of items where each item contains Mutation object and additional metadata
        """

        from models import Protein, Mutation
        from database import get_or_create

        snv = make_snv_key(chrom, dna_pos, dna_ref, dna_alt)

        items = [
            decode_csv(item)
            for item in self[snv]
        ]

        # this could be speed up by: itemgetters, accumulative queries and so on
        for item in items:

            protein = Protein.query.get(item['protein_id'])
            item['protein'] = protein

            mutation, created = get_or_create(
                Mutation,
                protein=protein,
                protein_id=protein.id,  # TODO: should use either protein or protein_id
                position=item['pos'],
                alt=item['alt']
            )
            item['mutation'] = mutation
            item['type'] = 'genomic'

        return items

    def iterate_known_muts(self):
        from models import Mutation
        from tqdm import tqdm

        for value in tqdm(self.values(), total=len(self.db)):
            for item in map(decode_csv, value):

                mutation = Mutation.query.filter_by(
                    protein_id=item['protein_id'],
                    position=item['pos'],
                    alt=item['alt']
                ).first()

                if mutation:
                    yield mutation


def make_snv_key(chrom, pos, ref, alt):
    """Makes a key for given `snv` (Single Nucleotide Variation)
    to be used as a key in hashmap in snv -> csv mappings.

    Args:
        chrom:
            str representing one of human chromosomes
            (like '1', '22', 'X'), e.g. one of returned
            by `helpers.bioinf.get_human_chromosomes`
        pos:
            int representing position of variation
        ref:
            char representing reference nucleotide
        alt:
            char representing alternative nucleotide
    """
    return ':'.join(
        (chrom, '%x' % int(pos))
    ) + ref.lower() + alt.lower()


def decode_csv(encoded_data):
    """Decode Coding Sequence Variant data from string made by encode_csv()."""
    strand, ref, alt, is_ptm = encoded_data[:4]
    cdna_pos, exon, protein_id = encoded_data[4:].split(':')
    cdna_pos = int(cdna_pos, base=16)
    return dict(zip(
        (
            'strand', 'ref', 'alt', 'pos',
            'cdna_pos', 'exon', 'protein_id', 'is_ptm'
        ),
        (
            strand, ref, alt, (cdna_pos - 1) // 3 + 1,
            cdna_pos, exon, int(protein_id, base=16), bool(int(is_ptm))
        )
    ))


def cdna_pos_from_aa(aa_pos):
    return (aa_pos - 1) * 3 + 1


def encode_csv(strand, ref, alt, cdna_pos, exon, protein_id, is_ptm):
    """Encode a Coding Sequence Variants into a single, short string.

    Args:
        strand: + or -
        ref: reference aminoacid residue
        alt: alternative aminoacid residue
        cdna_pos: position of mutation in cDNA coordinates;
             - aminoacid positions can be derived applying: `(int(cdna_pos) - 1) // 3 + 1`
             - `cdna_pos` can be retrieved from aminoacid position using: `cdna_pos_from_aa`
        exon: 'EX1', 'EX2' or any string representing an exon identifier
        protein_id: identifier of a protein to which encoded mutation belongs
        is_ptm: boolean - do we have evidence or prediction that given mutation
                impacts any PTM site in nearby?

    ref and alt are aminoacids, but pos is a a
    """
    return strand + ref + alt + ('1' if is_ptm else '0') + ':'.join((
        '%x' % int(cdna_pos), exon, '%x' % protein_id))
