from collections import defaultdict
from functools import partial

from helpers.plots import bar_plot, stacked_bar_plot
from models import MC3Mutation, InheritedMutation, SiteType, AnySiteType

from ..store import cases
from .common import site_types_with_any


def most_mutated_sites(sources, site_type: SiteType=AnySiteType, intersection=False, stacked=False, limit=20, filters=None):
    from analyses.enrichment import most_mutated_sites

    most_mutated = partial(most_mutated_sites, site_type=site_type, limit=limit, mutation_filter=filters)

    def create_track(sites, counts):
        return (
            [f'{site.protein.gene_name} {site.position}{site.residue}' for site in sites],
            counts
        )

    if not stacked or intersection:
        results = most_mutated(sources, intersection=intersection).all()
        if not results:
            return [], []
        sites, counts = zip(*results)
        return create_track(sites, counts)

    assert len(sources) == 2

    # so there are three tracks to stack: only ClinVar, only MC3, MC3 intersection ClinVar
    results = {}

    tracks = [
        (sources[:1], False, sources[1:]),  # e.g. ClinVar
        (sources, True, False),             # MC3 intersection ClinVar
        (sources[1:], False, sources[:1]),  # e.g. MC3
    ]

    site_track_count = defaultdict(dict)
    track_names = []

    for sources, intersection, exclusive in tracks:

        query = most_mutated(sources, intersection=intersection, exclusive=exclusive)
        track_name = ' and '.join([source.name for source in sources])
        track_names.append(track_name)

        for site, count in query:
            site_track_count[site][track_name] = count

    # take top X sites:

    def sum_of_counts(site_data):
        site, counts_by_track = site_data
        return sum(counts_by_track.values())

    sorted_sites = sorted(
        site_track_count.items(),
        key=sum_of_counts,
        reverse=True
    )

    # tracks with sites limited to the top sites
    limited_tracks_data = defaultdict(list)

    for site, site_data in sorted_sites[:limit]:
        for track_name in track_names:
            count = site_data.get(track_name, 0)
            limited_tracks_data[track_name].append((site, count))

    for track_name, data in limited_tracks_data.items():
        sites, counts = zip(*data)
        results[track_name] = create_track(sites, counts)

    return results


@cases(site_type=site_types_with_any)
@bar_plot
def mc3(site_type):
    return most_mutated_sites([MC3Mutation], site_type)


clinvar_subsets = {
    'all': None,
    'strict': InheritedMutation.significance_filter('strict'),
    'not_benign': InheritedMutation.significance_filter('not_benign')
}
clinvar_cases = cases(site_type=site_types_with_any, subset=clinvar_subsets).set_mode('product')


@clinvar_cases
@bar_plot
def clinvar(site_type, subset):
    return most_mutated_sites([InheritedMutation], site_type, filters=clinvar_subsets[subset])


@clinvar_cases
@stacked_bar_plot
def mc3_and_clinvar(site_type, subset):
    return most_mutated_sites(
        [MC3Mutation, InheritedMutation],
        site_type,
        stacked=True,
        filters=clinvar_subsets[subset]
    )


@clinvar_cases
@bar_plot
def mc3_and_clinvar_intersection(site_type, subset):
    return most_mutated_sites(
        [MC3Mutation, InheritedMutation],
        site_type,
        intersection=True,
        filters=clinvar_subsets[subset]
    )

