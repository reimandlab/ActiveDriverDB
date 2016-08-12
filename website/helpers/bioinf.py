basic_mappings = {'A': 'T', 'T': 'A', 'C': 'G', 'G': 'C'}
IUPAC_mappings = {'A': 'T', 'T': 'A', 'C': 'G', 'G': 'C', 'U': 'A', 'Y': 'R',
                  'R': 'Y', 'S': 'S', 'W': 'W', 'K': 'M', 'M': 'K', 'B': 'V',
                  'V': 'B', 'D': 'H', 'H': 'D', 'N': 'N'}


def complement(seq):
    """Get complement to given sequence.

    Sequence can be given as a string of basic four characters (ATCG)
    representing nucleotides or of full set of IUPAC accepted symbols.
    The sequence has to be witouth gaps or maskings & has to be upper case.
    """
    try:
        return ''.join([basic_mappings[n] for n in seq])
    except KeyError:
        return ''.join([IUPAC_mappings[n] for n in seq])


def get_human_chromosomes():
    """Return set of strings representing names of human chromosomes and MT.

    1-22 (inclusive), X, Y and mitochondrial
    """
    return set([str(x) for x in range(1, 23)] + ['X', 'Y', 'MT'])


def decode_mutation(mut):
    """Return tuple with: reference residue, position and alternative residue.

    Also, if assertions are enabled checks correctnes of the mutation.
    """
    assert mut[1] == '.'
    result = (mut[2], int(mut[3:-1]), mut[-1])
    return result


def decode_raw_mutation(mut):
    """Return tuple with: reference residue, position and alternative residue."""
    result = (mut[0], int(mut[1:-1]), mut[-1])
    return result
