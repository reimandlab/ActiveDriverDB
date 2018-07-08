from imports.cms import BadWordsImporter


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
