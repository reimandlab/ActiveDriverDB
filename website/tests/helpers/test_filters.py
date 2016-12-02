import pytest
import helpers.filters as filters


class Model:

    def __init__(self, value):
        self.value = value


def test_select_filter():

    test_objects = [
        Model('a'),
        Model('a'),
        Model('b'),
        Model('b'),
        Model('c'),
    ]

    tested_filter = filters.Filter(
        Model, 'value', comparators=['in'],
        choices=['a', 'b', 'c', 'd'],
        default='a', nullable=False,
    )

    # test the default value
    assert len(tested_filter.apply(test_objects)) == 2

    test_values = (
        ('b', 2),
        ('c', 1),
        ('d', 0)
    )

    for value, length in test_values:
        tested_filter.update(value)
        assert len(tested_filter.apply(test_objects)) == length

    with pytest.raises(filters.ValidationError):
        tested_filter.update('e')
        tested_filter.apply(test_objects)


def test_multiselect_filter():

    test_objects = [
        Model(['a']),
        Model(['a']),
        Model(['b']),
        Model(['b']),
        Model(['c']),
        Model(['a', 'c']),
        Model(['b', 'a']),
    ]

    tested_filter = filters.Filter(
        Model, 'value', comparators=['in'],
        choices=['a', 'b', 'c', 'd'],
        default='a', nullable=False,
        multiple='any'
    )

    test_values = (
        ('b', 3),
        ('c', 2),
        ('d', 0),
        (['a', 'b', 'c'], 7),
        (['a', 'c'], 5),
        (['b', 'c'], 5)
    )

    # test the default value
    assert len(list(tested_filter.apply(test_objects))) == 4

    with pytest.raises(filters.ValidationError):
        tested_filter.update('e')
        tested_filter.apply(test_objects)

    for value, length in test_values:
        tested_filter.update(value)
        assert len(list(tested_filter.apply(test_objects))) == length
