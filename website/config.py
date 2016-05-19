import os
base_dir = os.path.abspath(os.path.dirname(__file__))
databases_dir = os.path.join(base_dir, 'databases')


SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(databases_dir, 'app.db')
SQLALCHEMY_TRACK_MODIFICATIONS = True
# SQLALCHEMY_ECHO = False
SECRET_KEY = '\xfb\x12\xdf\xa1@i\xd6>V\xc0\xbb\x8fp\x16#Z\x0b\x81\xeb\x16'
DEBUG = True
DEFAULT_HOST = '0.0.0.0'    # use public IPs
DEFAULT_PORT = 5000
