from testing import ModelTest
from models import ShortURL
import pytest


class ShortURLTest(ModelTest):

    def test_encode_decode(self):
        base = ShortURL.base
        ids_to_test = (
            1, 2, 9, 10, 11, 15, 89, 1000, 999, 998, 8765431234567,
            base, base - 1, base + 1, base * 2, base * 2 - 1, base * base
        )
        for test_id in ids_to_test:
            print(test_id, 1)
            encoded = ShortURL(id=test_id, address='some_address').shorthand
            print(test_id, 2)
            decoded = ShortURL.shorthand_to_id(encoded)
            print(test_id, 3)
            assert decoded == test_id

        with pytest.raises(ValueError):
            ShortURL(id=0, address='some_address').shorthand
