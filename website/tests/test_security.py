import security

raw_hash = '$pbkdf2-sha512$1000$jRHC.J/zPidkzDkn5JwTQg$BwVXd2rjWquUENNG/6pesPn0PIGIWYJ.W75tqIwSi5ICSUeItwOPJ3yHvT1U6w4HGxr3IWpXHe33C.8IoanFxQ'


def test_pepper():
    assert security.PEPPER


def test_condiment():
    salt = 'salt'
    assert security.condiment(salt) != salt


def test_extract_salt():
    assert security.extract_salt(raw_hash) == "\x8d\x11\xc2\xf8\x9f\xf3>'d\xcc9'\xe4\x9c\x13B"


def test_replace_salt():
    salt = 'salt'
    prefix = '$pbkdf2-sha512$1000$'
    suffix = '$BwVXd2rjWquUENNG/6pesPn0PIGIWYJ.W75tqIwSi5ICSUeItwOPJ3yHvT1U6w4HGxr3IWpXHe33C.8IoanFxQ'
    expected = prefix + security.ab64_encode(salt) + suffix
    assert security.replace_salt(raw_hash, salt) == expected


def test_random_base64():
    for size in [20, 50, 100]:
        result = security.random_base64(size)
        print result
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


def test_new_salt_not_empty():
    new_salt = security.new_salt()
    assert new_salt


def test_new_salt_is_str():
    new_salt = security.new_salt()
    assert type(new_salt) == str


def test_new_salt_is_proper_length():
    """
    It ought be at least 100 characters - during 'serialization'
    to basecode initial length is expanding
    """
    new_salt = security.new_salt()
    assert len(new_salt) >= 100


def test_get_passlib_salt():
    """
    It ought be at least 100 characters - during 'serialization'
    to basecode initial length is expanding
    """
    salt = security.get_passlib_salt(50)
    print salt
    assert len(salt) >= 50


def test_generate_secret_hash():
    hash = security.generate_secret_hash('test_secret')
    assert hash


def test_generate_secret_hash_diference():
    """
    Don't allow secret to be a part of generated hash.
    It is possible for the test to fail, even if code is right, but then please,
    buy a ticket on a lottery, maybe you will win again.
    """
    secret = "Some long test secret so you won't need to spend money on the lottery."
    hash = security.generate_secret_hash(secret)
    assert secret not in hash


def test_verify_secret_success():
    hash = '$pbkdf2-sha512$1000$7h1DyFlrjXHOuXduLWUs5VyrFcLY.38vZQyBMAbAuPdeKyWEsNYaA4AwZozR.p/TWmtTc3BRc2RVRXJtUVB6RXU3QS1acURfMncwTmQ5QXFGSld5MmVTLTBIcFpTNG1jWDdwQUx0TXdlUkNhZEhoS2FlMjNJPQ$o4au842aG6xWJH8up4a8ER1ZYJ1H4P6ntjtUSixPaN2wNz3ecya8EIkRvdKoXf8CSxD38Ot4GPbCPPmt5/Ftcg'
    correct_secret = 'soME_S3CRe71j9d2@(ND(!@wedsf)ds)'

    security.PEPPER = 'liJUVcf7p2y94N3Xsyc18JSYexfIRyM8kKAxdNM4LUWnrFxjtIN4j0sZjInblDuUR0rETIGkF7p1VY25'
    assert security.verify_secret(correct_secret, hash)


def test_verify_secret_fail():
    hash = '$pbkdf2-sha512$1000$7h1DyFlrjXHOuXduLWUs5VyrFcLY.38vZQyBMAbAuPdeKyWEsNYaA4AwZozR.p/TWmtTc3BRc2RVRXJtUVB6RXU3QS1acURfMncwTmQ5QXFGSld5MmVTLTBIcFpTNG1jWDdwQUx0TXdlUkNhZEhoS2FlMjNJPQ$o4au842aG6xWJH8up4a8ER1ZYJ1H4P6ntjtUSixPaN2wNz3ecya8EIkRvdKoXf8CSxD38Ot4GPbCPPmt5/Ftcg'
    correct_secret = 'soME_S3CRe71j9d2@(ND(!@wedsf)ds)'

    security.PEPPER = 'liJUVcf7p2y94N3Xsyc18JSYexfIRyM8kKAxdNM4LUWnrFxjtIN4j0sZjInblDuUR0rETIGkF7p1VY25'

    import random
    import string

    for i in range(100):
        found = False
        while not found:
            some_secret = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(i))
            if some_secret != correct_secret:
                found = True
                assert not security.verify_secret(some_secret, hash)
