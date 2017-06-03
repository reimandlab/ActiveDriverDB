import pytest
import helpers.widgets as widgets


def test_widget():
    simple_widget = widgets.Widget(
        'Name of a widget',
        'radio',
        ['True', 'False'],
        'Mutation[is_ptm]',
        value='True'
    )

    assert simple_widget.is_active
    assert simple_widget.visible
    assert simple_widget.target_name == 'Mutation[is_ptm]'
    assert simple_widget.title == 'Name of a widget'

    # there is no single label for the simple widget
    with pytest.raises(Exception):
        assert simple_widget.label

    # there will be a single label here
    widget = widgets.Widget('name', 'checkbox', [0], 'Target', labels=['My label'])
    assert widget.label == 'My label'

    # if more than one label was given, we do not have a single label
    widget = widgets.Widget('name', 'select_multiple', ['x', 'y'], 'Target', labels=[
        'My label', 'Should not be there if I want to access .label'
    ])
    with pytest.raises(Exception):
        assert widget.label

    # it is forbidden to define a widget with a number of labels
    # greater than count of elements in the data
    with pytest.raises(ValueError):
        widgets.Widget('name', 'sth', [1, 2], 'target', labels=['a', 'b', 'c'])

    # labels are properly assigned to data when relying on lists order
    widget = widgets.Widget('name', 'sth', [1, 2], 'target', labels=['a', 'b'])
    items = dict(widget.items)
    assert items[1] == 'a'
    assert items[2] == 'b'

    # labels are properly assigned to data when using dict mapping
    widget = widgets.Widget('name', 'sth', [1, 2], 'target', labels={2: 'a', 1: 'b'})
    items = dict(widget.items)
    assert items[1] == 'b'
    assert items[2] == 'a'

    # data with 'None' label are hidden
    widget = widgets.Widget('name', 'sth', [1, 2], 'target', labels={1: 'a', 2: None})
    items = dict(widget.items)
    assert 2 not in items
