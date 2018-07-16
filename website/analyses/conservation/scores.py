from statistics import mean
from typing import List, Dict, Tuple, Iterable
from types import SimpleNamespace as Namespace

from pandas import DataFrame
import pyBigWig
from tqdm import tqdm as progress_bar


def no_progress_bar(iterator, *args, **kwargs):
    return iterator


class MismatchError(ValueError):
    pass


def gather_scores(score_tracks, regions_with_sites_by_protein, show_progress=True, verbose=True) -> List[float]:
    """Aggregate scores from given regions of given proteins into a single list"""
    all_scores = []
    skipped = set()
    progress = progress_bar if show_progress else no_progress_bar

    proteins_and_regions = progress(
        regions_with_sites_by_protein.items(),
        total=len(regions_with_sites_by_protein)
    )

    for protein, sites_interval in proteins_and_regions:
        try:
            scores = score_tracks[protein]
        except KeyError:
            skipped.add(protein)
            continue

        for i in sites_interval:
            score = scores[i]
            all_scores.append(score)

    if verbose and skipped:
        print('Skipped:', ', '.join([protein.gene.name for protein in skipped]))

    return all_scores


def extract_track(protein_data: DataFrame, protein, chrom: str, bw) -> List[float]:
    """Extract scores from given BigWig file for coding region of given protein.

    Scores for each nucleotide in the CDS will be returned,
    and the length of the track will be verified against
    the length of the protein x 3. The track will be oriented
    using strand information.

    Returns:
        scores in CDS space of given protein, without the scores for stop codon
    """

    protein_track = []

    for exon_start, exon_end in zip(protein_data.exonStarts, protein_data.exonEnds):
        # it's not interesting yet!
        if protein_data.cdsStart > exon_end:
            continue
        # already after the end!
        if protein_data.cdsEnd < exon_start:
            continue

        if protein_data.cdsStart > exon_start:
            # forced conversion to python int from np.int
            exon_start = int(protein_data.cdsStart)

        if protein_data.cdsEnd < exon_end:
            exon_end = int(protein_data.cdsEnd)

        assert exon_start < exon_end

        protein_track.extend(
            bw.values(chrom, exon_start, exon_end)
        )

    # let's remove the STOP codon
    protein_track = protein_track[:-3]

    matches = len(protein_track) == protein.length * 3

    if not matches:
        raise MismatchError(f'Track mismatches {protein}:', len(protein_track), protein.length * 3)

    direction = +1 if protein_data.strand == '+' else -1

    return protein_track[::direction]


def convert_to_aa_scores(nucleotide_scores: List[float]) -> List[float]:
    """Convert scores from CDS space into protein space, average scores per codon."""

    assert len(nucleotide_scores) % 3 == 0

    scores = []
    append = scores.append

    i, summed_score = 0, 0
    for score in nucleotide_scores:
        if i == 3:
            append(summed_score / 3)
            i = 0
            summed_score = 0
        i += 1
        summed_score += score
    assert i == 3
    append(summed_score / 3)

    return scores


def scores_for_proteins(proteins: Iterable, genes_data: DataFrame, big_wig_path: str) -> Tuple[Dict, Namespace]:
    """Load conservation scores, average when needed, and transform into protein space."""

    bw = pyBigWig.open(big_wig_path)

    score_tracks = {}
    skipped_premature = set()
    skipped_key_error = set()
    mapping_to_many = set()
    skipped_track_mismatch = set()

    for protein in progress_bar(proteins):

        if '*' in protein.sequence[:-1]:
            skipped_premature.add(protein)
            continue

        gene = protein.gene
        chrom = 'chr' + gene.chrom
        try:
            protein_data = genes_data.loc[[(chrom, protein.refseq)]]
        except KeyError:
            skipped_key_error.add(protein)
            continue

        protein_tracks = []

        # transcript might map to more than one genomic locations
        for genomic_location in protein_data.itertuples(index=False):

            try:
                track = extract_track(genomic_location, protein, chrom, bw)
            except MismatchError:
                skipped_track_mismatch.add(protein)
                continue
            except TypeError:
                skipped_key_error.add(protein)
                continue

            protein_tracks.append(track)

        protein_tracks = [track for track in protein_tracks if track]

        if not protein_tracks:
            continue
        elif len(protein_tracks) > 1:
            mapping_to_many.add(protein)
            protein_track = [
                mean(scores)
                for scores in zip(*protein_tracks)
            ]
        else:
            protein_track = protein_tracks[0]

        score_tracks[protein] = convert_to_aa_scores(protein_track)

    print(f'Averaged data for {len(mapping_to_many)} proteins mapping to more than one genomic location.')
    # print({protein.refseq for protein in mapping_to_many})

    print(f'Skipped {len(skipped_premature)} proteins with premature stop codons.')
    # print({protein.gene.name for protein in skipped_premature})

    print(f'Failed to find genomic data for {len(skipped_key_error)} proteins.')
    # print({(protein.gene.name, protein.gene.chrom, protein.gene.strand) for protein in skipped_key_error})

    print(f'Conflicting genomic and protein level coordinates for {len(skipped_track_mismatch)} proteins.')
    # print({protein.gene.name for protein in skipped_track_mismatch})

    details = Namespace(
        mapping_to_many_regions=mapping_to_many,
        skipped=Namespace(
            premature_stop_codon=skipped_premature,
            no_genomic_data=skipped_key_error,
            track_mismatch=skipped_track_mismatch
        )
    )

    return score_tracks, details
