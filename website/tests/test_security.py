import security


def test_random_base64():
    for size in [20, 50, 100]:
        result = security.random_base64(size)
        assert len(result) >= size


def test_generate_csrf_token():
    token = security.generate_csrf_token()
    assert token


def test_generate_csrf_token_length():
    """
    We still want at least 20 characters of Base64 as for 2016
    http://security.stackexchange.com/questions/6957/length-of-csrf-token
    """
    token = security.generate_csrf_token()
    assert len(token) >= 20
