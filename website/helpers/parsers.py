from tqdm import tqdm


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


def count_lines(filename):
    """Returns number of lines in a given file."""
    with open(filename) as file_object:
        return sum(1 for line in file_object)


def parse_tsv_file(filename, parser, file_header=False):
    """Utility function wraping file parser

    It opens file, provides progress bar, and checks if the file header is the
    same as given (if provided). For each line parser will be called.
    """
    with open(filename) as f:
        header = f.readline().rstrip().split('\t')
        if file_header:
            assert header == file_header
        for line in tqdm(f, total=count_lines(filename)):
            line = line.rstrip().split('\t')
            parser(line)


def parse_fasta_file(filename, parser):
    with open(filename) as f:
        for line in tqdm(f, total=count_lines(filename)):
            parser(line)

"""
def chunked_list(full_list, chunk_size=50):
    buffer = []
    for element in tqdm(full_list):
        buffer.append(element)
        if len(buffer) >= chunk_size:
            yield buffer
            buffer = []
    if buffer:
        yield buffer
"""
