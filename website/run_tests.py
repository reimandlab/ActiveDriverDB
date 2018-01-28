if [ $# -eq 0 ]
	then
		match="not data_dependent and not celery"
	else
		match="$1"
fi
python3 -m pytest -x -n 2 --cov=. -k "$match" -v
