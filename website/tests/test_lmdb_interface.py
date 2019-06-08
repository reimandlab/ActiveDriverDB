from database.lightning import LightningInterface


def test_basic_interface(tmpdir):
    db = LightningInterface(tmpdir)
    db[b'x'] = b'2'

    assert db[b'x'] == b'2'
    assert len(db) == 1

    db[b'y'] = b'3'
    assert db[b'y'] == b'3'
    assert len(db) == 2

    items_expected = {(b'x', b'2'), (b'y', b'3')}
    items_gathered = set()

    for key, value in db.items():
        items_gathered.add((key, value))

    assert items_expected == items_gathered
