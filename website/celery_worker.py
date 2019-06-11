from app import celery
from app import create_app

app = create_app(config_override={'HDB_READONLY': True, 'LOAD_VIEWS': False})
from search.task import search_task

celery
