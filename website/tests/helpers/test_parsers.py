from itertools import chain

import pytest
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


def test_parse_tsv_file(tmpdir):
    some_tsv_text_with_header = (
        'gene	id	some column with spaces',
        'XYZ	1	some description',
        'WQT	2	some description',
        'BCZ	3	some description',
    )
    temp_file = tmpdir.join('some_tsv_file.tsv')
    temp_file.write('\n'.join(some_tsv_text_with_header))
    file_name = str(temp_file)

    wrong_headers = (
        ['gene', 'id', 'some'],
        ['gene', 'id']
    )
    for wrong_header in wrong_headers:
        with pytest.raises(parsers.ParsingError):
            parsers.parse_tsv_file(
                file_name,
                lambda x: x,
                file_header=wrong_header
            )

    # test case 1: check if import goes well wih the test data
    counter = 0

    def parse(data):
        nonlocal counter
        counter += 1
        assert counter == int(data[1])
        assert data[2] == 'some description'

    parsers.parse_tsv_file(
        file_name,
        parse,
        file_header=['gene', 'id', 'some column with spaces']
    )

    counter = 0


def test_tsv_file_iterator(tmpdir):
    some_tsv_text = ('1', '2', '3', '4')
    temp_file = tmpdir.join('some_tsv_file.tsv')
    temp_file.write('\n'.join(some_tsv_text))
    file_name = str(temp_file)

    def test(**kwargs):
        return sum(parsers.tsv_file_iterator(file_name, **kwargs), [])

    assert ['2', '3', '4'] == test(skip=1)
    assert ['4'] == test(skip=3)
    assert ['3', '4'] == test(skip=2, limit=2)
    assert ['3'] == test(skip=2, limit=1)
