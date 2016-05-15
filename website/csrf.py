from flask import session, request, abort
from app import app
from security import generate_csrf_token


@app.before_request
def csrf_protect():
    if request.method == "POST":
        token = session.get('_csrf_token', None)

        if not token:
            abort(403)

        if 'X-Csrftoken' in request.headers:
            request_token = request.headers['X-Csrftoken']
        else:
            request_token = request.form.get('_csrf_token')

        if token != request_token:
            abort(403)


def new_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = generate_csrf_token()
    return session['_csrf_token']
