import pytest
import helpers.bioinf as bioinf
from collections import namedtuple


def test_complement():
    test_sequences = (
        ('ACTCGGTAA', 'TGAGCCATT'),
        ('TGAGCCATT', 'ACTCGGTAA'),
        ('TTAAGGCC', 'AATTCCGG'),
    )
    for sequence, complement in test_sequences:
        assert bioinf.complement(sequence) == complement


test_mutations = (
    ('c.G130A', ('G', 130, 'A')),
    ('p.V44I', ('V', 44, 'I')),
    ('c.C617T', ('C', 617, 'T')),
    ('p.S206L', ('S', 206, 'L')),
)

def test_decode_mutation():
    for mutation_string, result in test_mutations:
        assert bioinf.decode_mutation(mutation_string) == result


def test_decode_mutation_wrong():
    incorrect_mutations = ('p-F10A', 'pF10A')
    for mutation in incorrect_mutations:
        with pytest.raises(AssertionError):
            bioinf.decode_mutation(mutation)


def test_decode_raw_mutation():
    for mutation_string, result in test_mutations:
        raw_mutation_string = mutation_string[2:]
        assert bioinf.decode_raw_mutation(raw_mutation_string) == result


def test_get_human_chromosomes():
    chromosomes = bioinf.get_human_chromosomes()

    should_have = ['1',  '22',  'X',  'Y',  'MT']
    should_not_have = ['0',  '23']

    assert type(chromosomes) is set

    for chr in should_have:
        assert chr in chromosomes

    for chr in should_not_have:
        assert chr not in chromosomes


def test_determine_strand():

    test_data = {
        # (ref, cdna_ref, alt, cdna_alt): expected strand
        ('a', 'A', 'c', 'C'): '+',
        ('a', 'T', 'c', 'G'): '-',
        ('T', 'A', 'G', 'C'): '-',
        ('G', 'G', 'C', 'C'): '+'
    }
    for sequences, expected_result in test_data.items():
        assert bioinf.determine_strand(*sequences) == expected_result

    with pytest.raises(bioinf.DataInconsistencyError):
        assert bioinf.determine_strand('a', 'C', 'c', 'G')


def test_is_sequence_broken():

    Protein = namedtuple('Protein', 'refseq, sequence')
    p = Protein(refseq='NM_0001', sequence='MEAVPKKKKKK')

    not_broken_tuple = bioinf.is_sequence_broken(p, 1, 'M', 'A')
    assert not not_broken_tuple

    broken_tuple = bioinf.is_sequence_broken(p, 2, 'M', 'A')
    assert broken_tuple == ('NM_0001', 'E', 'M', '2', 'A')
