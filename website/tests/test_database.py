import database


def test_encode_csv():
    attributes = (
        # strand, ref, alt, cdna_pos, exon, protein_id, is_ptm
        '+', 'R', 'H', 204, 'exon1', 123, False
    )
    result = database.encode_csv(*attributes)
    assert result == '+RH0cc:exon1:7b'


def test_decode_csv():
    encoded_csv = '+RH0cc:exon1:7b'
    result = database.decode_csv(encoded_csv)
    assert result == dict(zip(
        ('strand', 'ref', 'alt', 'pos', 'cdna_pos', 'exon', 'protein_id', 'is_ptm'),
        ('+', 'R', 'H', 68, 204, 'exon1', 123, False)
    ))
