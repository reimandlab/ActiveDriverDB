from io import StringIO
from helpers import parsers


def test_count_lines():
    test_data = (
        ('first line', 1),
        ('first line\nsecond line', 2),
        ('first line\nsecond line\nthird line', 3),
    )
    for string, count in test_data:
        test_file = StringIO(string)
        assert count == parsers.count_lines(test_file)
