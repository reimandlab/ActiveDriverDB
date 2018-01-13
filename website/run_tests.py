python3 -m pytest -x -n 2 --cov=. -k 'not data_dependent and not celery' -v
