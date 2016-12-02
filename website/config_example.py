"""
This example config file provides basic configuration settings, enabling fast
deployment. Note that some values has to be changed due to security reason.

Those are:
    SECRET_KEY, SQLALCHEMY_BINDS (user, pass).

You should also consider using specific host address instead of default 0.0.0.0
Note that usually to host on port 80 or so you will need to have sudo access.

You should change the name of this file to `config.py`.
"""
SQLALCHEMY_BINDS = {
    'cms': 'mysql://user:pass@localhost/db_cms',
    'bio': 'mysql://user:pass@localhost/db_bio'
}
SQLALCHEMY_TRACK_MODIFICATIONS = True
SECRET_KEY = 'replace_this'
DEBUG = True
DEFAULT_HOST = '0.0.0.0'    # use public IPs
DEFAULT_PORT = 5000
JSONIFY_PRETTYPRINT_REGULAR = False
JSON_SORT_KEYS = False
