import passlib.hash
import base64
import os
from passlib.utils import ab64_encode, ab64_decode

"""
NOTE: On deplyment, always make sure, that passlib is installed in secure place,
and that the installation of the package is valid.
"""

hashh = passlib.hash.pbkdf2_sha512

# Pepper is not implemented in passlib 1.6.5, so we I've done it manually
PEPPER = str.encode(
	'liJUVcN3Xsyc18JSYexfIRyM8kKAxdNM4LUWnrFxjtIN4j0sZjInblDuUR0rETIGkF7p1VY25'
)


def condiment(salt):
	return salt + PEPPER


def replace_salt(hash, new_salt):
	return str.encode('$').join([
		ab64_encode(new_salt) if i == 3 else x
		for i, x in enumerate([str.encode(z) for z in hash.split('$')])
	])


def get_passlib_salt(size):
	raw_hash = hashh.encrypt('', salt_size=size)
	return extract_salt(raw_hash)


def extract_salt(raw_hash):
	"""
	passlib.hash.pbkdf2_* raw hashes are formated like:
		$pbkdf2-digest$rounds$salt$checksum
	so salt is on second third position
	"""
	substr = raw_hash.split('$')[3]
	return ab64_decode(str.encode(substr))


def random_base64(size=50):
	return base64.urlsafe_b64encode(os.urandom(size))


def new_salt():
	"""
	It's more reliable when using two sources to get a random salt than one.
	"""
	source_1 = get_passlib_salt(size=50)
	source_2 = random_base64(size=50)
	return source_1 + source_2


def generate_secret_hash(secret):
	"""
	Generates salted and peppered hash for given secret.
	Returns: raw_hash in passlib.hash.pbkdf2_ format, without pepper.
	Of course, to verify this construct, you need to modify
	salt in 'raw' with use of pepper.
	"""
	user_salt = new_salt()
	salt = condiment(user_salt)
	raw = hashh.encrypt(secret, salt=salt, rounds=1000)

	return replace_salt(raw, user_salt)


def verify_secret(secret, user_hash):

	user_salt = extract_salt(user_hash)
	salt = condiment(user_salt)
	hash = replace_salt(user_hash, salt)

	return hashh.verify(secret, hash)


def generate_csrf_token():
	return random_base64(size=25)
