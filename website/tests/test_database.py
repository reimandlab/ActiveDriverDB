import database
import genomic_mappings


def test_make_snv_key():
    test_data = (
        # chrom, pos, ref, alt
        (('1', '211', 'A', 'C'), ('1', '211', 'A', 'c')),
        (('X', '2012', 'T', 'G'), ('X', '2012', 't', 'g')),
    )
    for attributes, equivalent_attributes in test_data:
        result_1 = genomic_mappings.make_snv_key(*attributes)
        result_2 = genomic_mappings.make_snv_key(*equivalent_attributes)
        assert result_1 == result_2


def test_encode_csv():
    test_data = (
        # strand, ref, alt, cdna_pos, exon, protein_id, is_ptm
        (('+', 'R', 'H', 204, 'exon1', 123, False), '+RH0cc:exon1:7b'),
        (('-', 'R', 'H', 204, 'exon1', 123, True), '-RH1cc:exon1:7b'),
    )
    for attributes, correct_result in test_data:
        result = genomic_mappings.encode_csv(*attributes)
        assert result == correct_result


def test_decode_csv():
    keys = ('strand', 'ref', 'alt', 'pos', 'cdna_pos', 'exon', 'protein_id', 'is_ptm')
    test_data = (
        ('+RH0cc:exon1:7b', ('+', 'R', 'H', 68, 204, 'exon1', 123, False)),
        ('-RH1cc:exon1:7b', ('-', 'R', 'H', 68, 204, 'exon1', 123, True)),
    )
    for encoded_csv, correct_result in test_data:
        result = genomic_mappings.decode_csv(encoded_csv)
        assert result == dict(zip(keys, correct_result))
