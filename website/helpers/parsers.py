import os
from glob import glob
import gzip
from tqdm import tqdm


def get_files(path, pattern):
    """Get all files from given `path` matching to given pattern

    Patterns should be string expression with wildcards * following Unix style.
    """
    return glob(path + os.sep + pattern)


def read_from_gz_files(directory, pattern, skip_header=True):
    """Creates generator yielding subsequent lines from compressed '.gz' files

    Lines from each file will be decoded to 'latin1' and read in chunk of 10000
    lines each (to keep quite optimal memory usage / disk operations ratio),
    what allows huge files to be read with this function.

    Progress bar is embeded.
    """

    files = get_files(directory, pattern)

    for filename in tqdm(files, unit=' files'):

        with gzip.open(filename, 'rb') as f:

            if skip_header:
                next(f)

            for line in buffered_readlines(f, 10000):
                yield line.decode('latin1')


def buffered_readlines(file_handle, line_count=5000):
    """Works like a normal readline function but buffers reading operations.

    The number of lines to read in once is specified by `line_count`.
    """
    is_eof = False
    while not is_eof:
        buffer = []
        # read as much as line_count says
        for _ in range(line_count):
            line = file_handle.readline()

            # stop if needed
            if not line:
                is_eof = True
                break

            buffer.append(line)
        # release one row in a once from buffer
        for line in buffer:
            yield line


def count_lines(file_object):
    """Returns number of lines in a given file."""
    count = sum(1 for line in file_object)
    file_object.seek(0)   # return to the begining of the file
    return count


def parse_tsv_file(filename, parser, file_header=None):
    """Utility function wraping tsv (tab-separated values) file parser.

    It checks if the file header is the same as given (if provided).
    For each line parser will be called.

    Progress bar is embeded.
    """
    with open(filename) as f:
        data_lines_count = count_lines(f)
        if file_header:
            header = f.readline().rstrip().split('\t')
            data_lines_count -= 1
            assert header == file_header
        for line in tqdm(f, total=data_lines_count, unit=' lines'):
            line = line.rstrip().split('\t')
            parser(line)


def parse_text_file(filename, parser, file_header=None):
    """Utility function wraping raw text file parser.

    It checks if the file header is the same as given (if provided).
    For each line parser will be called.

    Progress bar is embeded.
    """
    with open(filename) as f:
        data_lines_count = count_lines(f)
        if file_header:
            header = f.readline().rstrip()
            data_lines_count -= 1
            assert header == file_header
        for line in tqdm(f, total=data_lines_count, unit=' lines'):
            line = line.rstrip()
            parser(line)


def parse_fasta_file(filename, parser):
    """Utility function wraping fasta file parser.

    For each line parser will be called.

    Progress bar is embeded.
    """
    with open(filename) as f:
        for line in tqdm(f, total=count_lines(f), unit=' lines'):
            parser(line)


def chunked_list(full_list, chunk_size=10000):
    """Creates generator with `full_list` splited into chunks.

    Each chunk will be no longer than `chunk_size` (the last chunk may have
    less elements if provided `full_list` is not divisable by `chunk_size`).

    Progress bar is embeded.
    """
    element_buffer = []
    for element in tqdm(full_list):
        element_buffer.append(element)
        if len(element_buffer) >= chunk_size:
            yield element_buffer
            element_buffer = []
    if element_buffer:
        yield element_buffer
