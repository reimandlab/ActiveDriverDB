from berkley_db import BerkleyHashSet


def are_the_same(view_one, view_two, cast):
    # this has some terrifying complexity, use only for testing

    view_one = list(map(cast, view_one))
    view_two = list(map(cast, view_two))
    print(view_two, view_one)

    return (
        all(elem in view_one for elem in view_two)
        and
        all(elem in view_two for elem in view_one)
    )


def test_berkley_hash_set(tmpdir):
    db_file = str(tmpdir.join('test-bhs.db'))
    bhs = BerkleyHashSet(db_file)

    # should be empty when first created
    assert dict(bhs.items()) == {}
    assert len(bhs) == 0

    # let say we store keywords relating to specific genes in bhs
    bhs['tp53'] = {'tumour', 'p53'}
    assert len(bhs) == 1

    # update set
    bhs['tp53'].update(['antigen', 'p53'])
    assert bhs['tp53'] == {'tumour', 'antigen', 'p53'}

    # add some values
    bhs.add('tp53', 'oligomerization domain')
    bhs.add('brca2', 'cancer')

    # update bhs
    bhs.update('brca2', {'breast', 'DNA repair'})

    expected_representation = {
        'tp53': {'tumour', 'antigen', 'p53', 'oligomerization domain'},
        'brca2': {'breast', 'cancer', 'DNA repair'}
    }

    def value_as_set(value):
        return set(map(str, value))

    def item_with_set(item):
        key, value = item
        return key, value_as_set(value)

    # values of bhs return iterator [per key] of iterators [per set item] (!)
    assert are_the_same(bhs.values(), expected_representation.values(), value_as_set)
    assert are_the_same(bhs.items(), expected_representation.items(), item_with_set)
