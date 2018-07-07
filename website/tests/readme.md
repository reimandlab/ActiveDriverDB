**How to test**

Tests are compatibile with both nose and pytest, but pytest does not require extra configuration to start.

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

**Tools installation**

Both nose and pytests are not installed by default. To get them, use pip3:

```bash
pip3 install nose pytest pytest-cov
```
