import security
from database_testing import DatabaseTest


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


class TestCSRF(DatabaseTest):

    def test_post_csrf(self):

        @self.app.route('/test/', methods=['GET', 'POST'])
        def test():
            from flask import jsonify
            return jsonify(True)

        # with token we should get response
        response = self.client.post('/test/', with_csrf_token=True)
        assert response.status_code == 200
        assert response.json is True

        # without token the request should abort with 403 status code
        response = self.client.post('/test/', with_csrf_token=False)
        assert response.status_code == 403

        # get request should be indifferent to token presence:
        response = self.client.get('/test/')
        assert response.status_code == 200
