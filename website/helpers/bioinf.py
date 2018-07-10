basic_mappings = {'A': 'T', 'T': 'A', 'C': 'G', 'G': 'C'}
IUPAC_mappings = {'A': 'T', 'T': 'A', 'C': 'G', 'G': 'C', 'U': 'A', 'Y': 'R',
                  'R': 'Y', 'S': 'S', 'W': 'W', 'K': 'M', 'M': 'K', 'B': 'V',
                  'V': 'B', 'D': 'H', 'H': 'D', 'N': 'N'}


# note: hydroxylysine mapped to K
aa_symbols = (
    'A', 'C', 'D', 'D', 'E', 'E', 'F', 'G', 'H', 'I', 'K', 'L', 'M', 'N', 'P', 'Q', 'R', 'S', 'T', 'V', 'W', 'Y', 'K'
)
aa_names = (
    'alanine', 'cysteine', 'aspartic acid', 'aspartate', 'glutamic acid', 'glutamate', 'phenylalanine', 'glycine',
    'histidine',
    'isoleucine', 'lysine', 'leucine', 'methionine', 'asparagine', 'proline', 'glutamine', 'arginine',
    'serine', 'threonine', 'valine', 'tryptophan', 'tyrosine', 'hydroxylysine'
)
aa_name_to_symbol = dict(zip(aa_names, aa_symbols))


class DataInconsistencyError(Exception):
    pass


def complement(seq):
    """Get complement to given sequence.

    Sequence can be given as a string of basic four characters (ATCG)
    representing nucleotides or of full set of IUPAC accepted symbols.
    The sequence has to be without gaps or maskings & has to be upper case.
    """
    try:
        return ''.join([basic_mappings[n] for n in seq])
    except KeyError:
        return ''.join([IUPAC_mappings[n] for n in seq])


def get_human_chromosomes():
    """Return set of strings representing names of human chromosomes and MT.

    1-22 (inclusive), X, Y and mitochondrial. Made as a function to enable easy
    re-factorization of chromosomes from strings to models if needed in future.
    """
    return set([str(x) for x in range(1, 23)] + ['X', 'Y', 'MT'])


def decode_mutation(mut):
    """Return tuple with: reference residue, position and alternative residue.

    Also, if assertions are enabled checks correctness of the mutation string.

    An example input string for this function is: p.R252H.
    No assertion about source of mutations is made: you can use c.C110T as well
    """
    assert mut[1] == '.'
    return mut[2], int(mut[3:-1]), mut[-1]


def decode_raw_mutation(mut):
    """Return tuple with: reference residue, position and alternative residue.

    An example input string for this function is: R252H, where:
        R is reference residue,
        252 is position of mutation,
        H is alternative residue,
    """
    return mut[0], int(mut[1:-1]), mut[-1]


def determine_strand(ref, cdna_ref, alt, cdna_alt):
    """Determine DNA strand +/- on which a gene with given cDNA sequence lies.

    Input requirements: cdna_ref/cdna_alt has to be uppercase.

    The function compares given ref/cdna_ref, alt/cnda_alt to deduce a strand.

    Returns a single character string:
        '+' for forward strand,
        '-' for reverse strand.
    Raises DataInconsistencyError for sequences which do not match.
    """
    ref, alt = ref.upper(), alt.upper()

    if cdna_ref == ref and cdna_alt == alt:
        return '+'
    elif complement(cdna_ref) == ref and complement(cdna_alt) == alt:
        return '-'
    else:
        raise DataInconsistencyError(
            f'Unable to determine strand for: {ref} {cdna_ref} {alt} {cdna_alt}'
        )


def is_sequence_broken(protein, test_pos: int, test_res: str, test_alt: str=None):
    """Check if (in given protein) there is given residue on given position.

    Returns:
        - False if sequence is not broken,
        - a tuple of identifying the problem if an inconsistency between sequences is detected.

    TODO: use test_alt to detect those ref -> alt transitions which are not possible?
    """
    sequence = protein.sequence
    if len(sequence) <= test_pos:
        return protein.refseq, '-', test_res, str(test_pos), test_alt
    else:
        ref_in_db = sequence[test_pos - 1]
        if test_res == ref_in_db:
            return False
        return protein.refseq, ref_in_db, test_res, str(test_pos), test_alt
