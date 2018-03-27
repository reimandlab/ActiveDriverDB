from pathlib import Path

from rpy2.robjects import StrVector, IntVector, r
from rpy2.robjects.packages import importr

from helpers.ggplot2 import GG

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
            'Unable to determine strand for: %s %s %s %s' %
            (ref, cdna_ref, alt, cdna_alt)
        )


def is_sequence_broken(protein, test_pos, test_res, test_alt=None):
    """Check if (in given protein) there is given residue on given position.

    Returns:
        - False if sequence is not broken,
        - a tuple of identifying the problem if an inconsistency between sequences is detected.

    TODO: use test_alt to detect those ref -> alt transitions which are not possible?
    """
    if len(protein.sequence) <= int(test_pos):
        return protein.refseq, '-', test_res, str(test_pos), test_alt
    else:
        ref_in_db = protein.sequence[int(test_pos) - 1]
        if test_res == ref_in_db:
            return False
        return protein.refseq, ref_in_db, test_res, str(test_pos), test_alt


def sequence_logo(pwm_or_seq, path: Path=None, width=369, height=149, dpi=72, legend=False, renumarate=True, title: str=None):
    """Generate a sequence logo from Position Weight Matrix (pwm)
    or a list of aligned sequences.

    and save it into a file if a path was provided.
    The logo will be generated with ggseqlogo (R).

    Args:
        renumarate:
            change the labels of x axis to reflect relative position
            to the modified (central) residue (15-aa sequence is assumed)
    """
    gglogo = importr("ggseqlogo")
    ggplot2 = importr("ggplot2")

    if isinstance(pwm_or_seq, list):
        pwm_or_seq = StrVector(pwm_or_seq)

    theme_options = {
        'legend.position': 'auto' if legend else 'none',
        'plot.title': ggplot2.element_text(hjust=0.5, size=16),
        'axis.title.y': ggplot2.element_text(size=16),
        'text': ggplot2.element_text(size=20),
        'plot.margin': r.unit([0.03, 0.045, -0.2, 0.06], 'in'),
    }

    plot = GG(gglogo.ggseqlogo(pwm_or_seq)) + ggplot2.theme(**theme_options) + ggplot2.labs(y='bits')

    if renumarate:
        plot += ggplot2.scale_x_continuous(breaks=IntVector(range(1, 14 + 2)), labels=IntVector(range(-7, 7 + 1)))
    if title:
        plot += ggplot2.ggtitle(title)

    if path:
        ggplot2.ggsave(str(path), width=width / dpi, height=height / dpi, dpi=dpi, units='in', bg='transparent')

    return plot
