from warnings import warn

import lmdb

from app import celery
from app import create_app

try:
    app = create_app(config_override={'HDB_READONLY': True, 'LOAD_VIEWS': False})
except lmdb.Error as e:
    if 'No such file or directory' in str(e):
        warn(
            'Did you forget to create the HDB databases first?'
            ' The celery worker uses HDB in read-only mode and cannot create them.'
            ' Invoke ./manage.py migrate to ensure all databases are created.'
        )
    raise
from search.task import search_task


__all__ = ['celery', 'search_task']
