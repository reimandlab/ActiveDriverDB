if [ $# -eq 0 ]
	then
		match="not test_import_results and not test_data and not celery"
	else
		match="$1"
fi
python3 -m pytest -x -n 1 --cov=. -k "$match" -vv -m 'serial'
python3 -m pytest -x -n 2 --cov=. -k "$match" -vv -m 'not serial'
