from models import ShortURL


def test_encode_decode():
    base = ShortURL.base
    ids_to_test = (
        0, 1, 2, 9, 10, 11, 15, 89, 1000, 999, 998, 8765431234567,
        base, base - 1, base + 1, base * 2, base * 2 - 1, base * base
    )
    for test_id in ids_to_test:
        encoded = ShortURL(id=test_id, address='some_address').shorthand
        decoded = ShortURL.shorthand_to_id(encoded)
        assert decoded == test_id
