from flask import abort
from flask import request
from flask import session
from app import app
from security import generate_csrf_token


@app.before_request
def csrf_protect():
    """Require CSRF authentication of requests sent with POST method."""

    if request.method == 'POST':
        token = session.get('_csrf_token', None)

        if not token:
            abort(403)

        if 'X-Csrftoken' in request.headers:
            request_token = request.headers['X-Csrftoken']
        else:
            request_token = request.form.get('_csrf_token')

        # comparison of binary form of the text differs among coding formats
        # (Python3 specific) so, let's use str(text) for comparison
        if str(token) != str(request_token):
            abort(403)


def new_csrf_token():
    """Create CSRF token for the session or return one (if already exists)."""

    if '_csrf_token' not in session:
        session['_csrf_token'] = generate_csrf_token()
    return session['_csrf_token']
