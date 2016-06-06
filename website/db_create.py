#!/usr/bin/env python3
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
