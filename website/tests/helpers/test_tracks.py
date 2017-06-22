from helpers.tracks import SequenceTrack
from models import Protein, Site


def test_prepare_tracks():
    protein = Protein(refseq='NM_01', sequence='123456789', sites=[Site(position=4)])
    sequence_track = SequenceTrack(protein)
    site = sequence_track.subtracks[0].elements[0]
    assert site.start >= 0


def test_trim_ends():
    # protein sequences are 1-based
    track = SequenceTrack(Protein(sequence='1234567890'))

    element = [-5, 10]  #
    track.trim_ends([element])
    assert element == [1, 4]

    element = [5, 10]   # 567890----
    track.trim_ends([element])
    assert element == [5, 6]    # should include 0
