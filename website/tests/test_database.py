import database


def test_encode_csv():
    test_data = (
        # strand, ref, alt, cdna_pos, exon, protein_id, is_ptm
        (('+', 'R', 'H', 204, 'exon1', 123, False), '+RH0cc:exon1:7b'),
        (('-', 'R', 'H', 204, 'exon1', 123, True), '-RH1cc:exon1:7b'),
    )
    for attributes, correct_result in test_data:
        result = database.encode_csv(*attributes)
        assert result == correct_result


def test_decode_csv():
    keys = ('strand', 'ref', 'alt', 'pos', 'cdna_pos', 'exon', 'protein_id', 'is_ptm')
    test_data = (
        ('+RH0cc:exon1:7b', ('+', 'R', 'H', 68, 204, 'exon1', 123, False)),
        ('-RH1cc:exon1:7b', ('-', 'R', 'H', 68, 204, 'exon1', 123, True)),
    )
    for encoded_csv, correct_result in test_data:
        result = database.decode_csv(encoded_csv)
        assert result == dict(zip(keys, correct_result))
