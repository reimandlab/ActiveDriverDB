from tempfile import NamedTemporaryFile

import pytest


def make_named_temp_file(data=None, mode='w', opener=open):
    """Create temporary file and return path to it.

    Args:
        data: if given, the data will be written to file
        mode: mode in which file should be created (w, wb etc)
    """
    temp_file = NamedTemporaryFile(mode=mode, delete=False)

    temp_file.close()
    name = temp_file.name

    if data:
        with opener(name, mode) as f:
            f.write(data)

    return name


use_fixture = pytest.fixture(autouse=True)