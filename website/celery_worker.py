from app import celery
from app import create_app

app = create_app(config_override={'BDB_MODE': 'r'})
celery
