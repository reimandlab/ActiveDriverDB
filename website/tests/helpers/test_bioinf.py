import pytest
import helpers.bioinf as bioinf


def test_complement():
    test_sequences = (
        ('ACTCGGTAA', 'TGAGCCATT'),
        ('TGAGCCATT', 'ACTCGGTAA'),
        ('TTAAGGCC', 'AATTCCGG'),
    )
    for sequence, complement in test_sequences:
        assert bioinf.complement(sequence) == complement


def test_decode_mutation():
    test_mutations = (
        ('c.G130A', ('G', 130, 'A')),
        ('p.V44I', ('V', 44, 'I')),
        ('c.C617T', ('C', 617, 'T')),
        ('p.S206L', ('S', 206, 'L')),
    )
    for mutation_string, result in test_mutations:
        assert bioinf.decode_mutation(mutation_string) == result


def test_decode_mutation_wrong():
    incorrect_mutations = ('p-F10A', 'pF10A')
    for mutation in incorrect_mutations:
        with pytest.raises(AssertionError):
            bioinf.decode_mutation(mutation)
