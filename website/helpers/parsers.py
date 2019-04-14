import os
from contextlib import contextmanager
from glob import glob
import gzip
from tqdm import tqdm
import subprocess


class ParsingError(Exception):
    """Generic exception thrown by a parser."""
    pass


def gzip_open_text(path, mode=None):
    if not mode:
        mode = 'rt'
    else:
        mode += 't'
    return gzip.open(path, mode)


def get_files(path, pattern):
    """Get all files from given `path` matching to given pattern

    Patterns should be string expression with wildcards * following Unix style.
    """

    return glob(path + os.sep + pattern)


@contextmanager
def fast_gzip_read(file_name, mode='r', processes=4, as_str=False):
    if mode != 'r':
        raise ValueError('Only "r" mode is supported')

    command = 'pigz -d -p ' + str(processes) + ' -c %s'

    p = subprocess.Popen(
        (command % file_name).split(' '),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=as_str
    )
    yield p.stdout


def read_from_gz_files(directory, pattern, skip_header=True, after_batch=lambda: None):
    """Creates generator yielding subsequent lines from compressed '.gz' files

    Progress bar is embedded.
    """

    files = get_files(directory, pattern)

    for filename in tqdm(files, unit=' files'):

        with fast_gzip_read(filename, processes=4, as_str=True) as f:

            if skip_header:
                next(f)         # TODO: force header checking, this allows errors to pass silently!

            for line in f:
                yield line

        after_batch()


def count_lines(file_object):
    """Returns number of lines in a given file."""
    count = sum(1 for _ in file_object)
    file_object.seek(0)   # return to the beginning of the file
    return count


def iterate_tsv_gz_file(
        filename, file_header=None
):
    """Utility iterator for gzipped tsv (tab-separated values) file.

    It checks if the file header is the same as given (if provided).

    Progress bar is embedded.
    """
    with fast_gzip_read(filename) as f:
        data_lines_count = sum(1 for _ in f)

    with fast_gzip_read(filename) as f:
        if file_header:
            header = f.readline().decode('utf-8').rstrip().split('\t')
            data_lines_count -= 1
            if header != file_header:
                raise ParsingError(
                    'Given file header does not match to expected: '
                    'expected: %s, found: %s' % (file_header, header)
                )
        for line in tqdm(f, total=data_lines_count, unit=' lines'):
            line = line.decode('utf-8').rstrip().split('\t')
            yield line


def tsv_file_iterator(
    filename, file_header=None, file_opener=open, mode='r'
):
    with file_opener(filename, mode=mode) as f:
        data_lines_count = count_lines(f)

    with file_opener(filename, mode=mode) as f:
        if file_header:
            header = f.readline().rstrip().split('\t')
            data_lines_count -= 1
            if header != file_header:
                raise ParsingError(
                    'Given file header does not match to expected: '
                    'expected: %s, found: %s' % (file_header, header)
                )

        for line in tqdm(f, total=data_lines_count, unit=' lines'):
            yield line.rstrip().split('\t')


def parse_tsv_file(
    filename, parser, file_header=None, file_opener=open, mode='r'
):
    """Utility function wrapping tsv (tab-separated values) file parser.

    It checks if the file header is the same as given (if provided).
    For each line parser will be called.

    Progress bar is embedded.
    """
    for line in tsv_file_iterator(filename, file_header, file_opener, mode):
        parser(line)


def parse_text_file(filename, parser, file_header=None, file_opener=open):
    """Utility function wrapping raw text file parser.

    It checks if the file header is the same as given (if provided).
    For each line parser will be called.

    Progress bar is embedded.
    """
    with file_opener(filename) as f:
        data_lines_count = count_lines(f)
        if file_header:
            header = f.readline().rstrip()
            data_lines_count -= 1
            if header != file_header:
                raise ParsingError
        for line in tqdm(f, total=data_lines_count, unit=' lines'):
            line = line.rstrip()
            parser(line)


def parse_fasta_file(filename, on_sequence, on_header=lambda x: x, file_opener=open, mode='r'):
    """Utility function wrapping Fasta file parser.

    For each line parser will be called.

    Progress bar is embedded.
    """
    header = None

    with file_opener(filename, mode) as f:
        for line in tqdm(f, total=count_lines(f), unit=' lines'):
            line = line.rstrip()
            if line.startswith('>'):
                header = on_header(line[1:])
            else:
                on_sequence(header, line)


def chunked_list(full_list, chunk_size=10000):
    """Creates generator with `full_list` slitted into chunks.

    Each chunk will be no longer than `chunk_size` (the last chunk may have
    less elements if provided `full_list` is not divisible by `chunk_size`).

    Progress bar is embedded.
    """
    element_buffer = []
    for element in tqdm(full_list):
        element_buffer.append(element)
        if len(element_buffer) >= chunk_size:
            yield element_buffer
            element_buffer = []
    if element_buffer:
        yield element_buffer
