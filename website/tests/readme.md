**How to test**

Tests are compatible with both nose and pytest, but pytest does not require extra configuration to start.

To run tests with pytest, type:
```bash
~/website$ python3 -m pytest
```

To checkout coverage, install pytest-cov and run:
```bash
~/website$ python3 -m pytest --cov=.
```


You can exclude third-party code integrated into you installation (if any exists) creating .coveragerc file with contents like:

```conf
[run]
omit =
    flask_sqlalchemy/*
    tests/*
```

And then running:

```bash
~/website$ python3 -m pytest --cov=. --cov-config .coveragerc
```


Parallel testing is possible thanks to `pytest-xdist`.

**Recommended command for development testing**

The ultimate and recommended command to test the app is:
```bash
python3 -m pytest -x --cov=. -n 4 -k 'not data_dependent'
```

It uses 4 cores, stops after first failure, excludes data dependent tests and generates coverage report.


**Tools installation**

Pytest and its plugins are not installed by default. To get them, use pip3:

```bash
pip3 install -r tests/requirements.txt
```
