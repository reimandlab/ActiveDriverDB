from imports.protein_data import load_bad_words     # TODO Move this out of imports.protein_data


def test_cms(tmpdir):
    words = [
        'bad-word',
        'very-bad-word',
        'other-word',
    ]
    temp_file = tmpdir.join('some_bad_words.txt')
    temp_file.write('\n'.join(words))
    bad_words = load_bad_words(str(temp_file))

    assert len(bad_words) == 3

    for i, word in enumerate(words):
        assert bad_words[i].word == word
