import passlib.hash
import base64
import os

"""
On deplyment, always make sure, that passlib is installed in secure place,
and that the installation of the package is valid.
"""

hashh = passlib.hash.pbkdf2_sha512


def random_base64(size=50):
    return base64.urlsafe_b64encode(os.urandom(size))


def generate_secret_hash(secret):
    return hashh.encrypt(secret, rounds=1000)


def verify_secret(secret, user_hash):
    return hashh.verify(secret, user_hash)


def generate_csrf_token():
    return random_base64(size=25)
