from tempfile import NamedTemporaryFile


def make_named_temp_file(data=None,  mode='w'):
    """Create temporary file and return path to it.

    Args:
        data: if given, the data will be written to file
        mode: mode in which file should be created (w, wb etc)
    """
    temp_file = NamedTemporaryFile(mode=mode, delete=False)

    if data:
        temp_file.write(data)
    temp_file.close()

    return temp_file.name
