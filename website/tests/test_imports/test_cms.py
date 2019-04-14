from pytest import warns

from database_testing import DatabaseTest
from database import db
from imports.cms import BadWordsImporter
from imports.cms import IndexPage


def test_cms(tmpdir):
    words = [
        'bad-word',
        'very-bad-word',
        'other-word',
    ]
    temp_file = tmpdir.join('some_bad_words.txt')
    temp_file.write('\n'.join(words))
    importer = BadWordsImporter()
    bad_words = importer.load(str(temp_file))

    assert len(bad_words) == 3

    for i, word in enumerate(words):
        assert bad_words[i].word == word


class TestImport(DatabaseTest):

    def test_index_page(self):

        # test loading when the index page is absent
        importer = IndexPage()
        page, = importer.load()
        assert page.address == 'index'
        db.session.add(page)

        # and in case if the index page is already there
        with warns(UserWarning, match='Index page already exists, skipping...'):
            importer.load()
