import pytest
import helpers.filters as filters


class Model:

    def __init__(self, value):
        self.value = value


def test_filter():

    # Test initialization

    with pytest.raises(filters.InitializationError):
        filters.Filter(
            Model, 'value', comparators=['this is not a comparator'],
            choices=['a', 'b', 'c', 'd'],
            default='a', nullable=False,
        )

    # Test is_active property

    test_values = (
        # if there is *any* value, the filter should be active
        (False, True, True),
        (False, False, True),
        (True,  True, True),
        (True,  False, True),
        # if the value is None, filter is disabled
        (None,  None, False),
        # But if it has some value, it's not!
        (None,  True, True),
        (None,  False, True)
    )

    for default, value, should_be_active in test_values:
        tested_filter = filters.Filter(
            Model, 'value', comparators=['eq'],
            default=default
        )
        tested_filter.update(value)
        assert tested_filter.is_active == should_be_active


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
    assert len(list(tested_filter.apply(test_objects))) == 2

    test_values = (
        ('b', 2),
        ('c', 1),
        ('d', 0)
    )

    for value, length in test_values:
        tested_filter.update(value)
        assert len(list(tested_filter.apply(test_objects))) == length

    with pytest.raises(filters.ValidationError):
        tested_filter.update('e')
        tested_filter.apply(test_objects)

    tested_filter = filters.Filter(
        Model, 'value', comparators=['in'],
        choices=['a', 'b'],
        nullable=True,
    )

    tested_filter.update(None)
    # the filter should indicate that it's turned off when updated with None
    # and no default value is set
    assert tested_filter.apply(test_objects) == -1


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


def test_url_string():

    manager = filters.FilterManager(
        [
            filters.Filter(
                Model, 'color', comparators=['eq'],
                default='red'
            ),
            filters.Filter(
                Model, 'shape', comparators=['eq']
            )
        ]
    )

    assert manager.url_string() == None
    assert manager.url_string(expanded=True) == 'Model.color:eq:red'

    manager.filters['Model.shape'].update('rectangle')
    assert manager.url_string() == 'Model.shape:eq:rectangle'

    assert all(
        sub in manager.url_string(expanded=True)
        for sub in ('Model.color:eq:red', 'Model.shape:eq:rectangle')
    )

    manager.filters['Model.color'].update('blue')
    assert all(
        sub in manager.url_string()
        for sub in ('Model.color:eq:blue', 'Model.shape:eq:rectangle')
    )
    assert manager.url_string() == manager.url_string(expanded=True)

    manager.filters['Model.color'].update(None)
    assert manager.url_string() == 'Model.shape:eq:rectangle'
    assert all(
        sub in manager.url_string(expanded=True)
        for sub in ('Model.color:eq:red', 'Model.shape:eq:rectangle')
    )

    manager.filters['Model.color'].visible = False
    assert manager.url_string(expanded=True) == 'Model.shape:eq:rectangle'

    manager.filters['Model.shape'].update(None)
    assert manager.url_string() == None
    assert manager.url_string() == manager.url_string(expanded=True)
