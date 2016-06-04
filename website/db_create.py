""""
In case of exception:
    InvalidRequestError: Table '(some name)' is
    already defined for this MetaData instance
just comment out part of app.py where import of views (and what comes
along - models) occurs - it has to be the very end of the file.
"""
from database import db
from import_data import import_data

print('Removing relational database...')
db.reflect()
db.drop_all()
print('Removing relational database completed.')

print('Recreating relational database...')
db.create_all()
print('Recreating relational database completed.')

print('Importing data')
import_data()
print('Importing completed')

print('Done, databases reset completed.')
