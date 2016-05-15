from app import db
from import_data import import_data

print('Removing relational database...')
# http://jrheard.tumblr.com/post/12759432733/dropping-all-tables-on-postgres-using
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

