import re
from collections import defaultdict, namedtuple
from typing import Pattern

from tqdm import tqdm

from models import Site, SiteType, Mutation


def compile_motifs(motifs: dict):
    for key, value in motifs.items():
        if isinstance(value, dict):
            motifs[key] = compile_motifs(value)
        else:
            motifs[key] = re.compile(value)
    return motifs


all_motifs = compile_motifs({
    # motifs or rather sequons:
    'glycosylation': {
        'N-glycosylation': 'N[^P][ST]',     # https://prosite.expasy.org/PDOC00001
        'Atypical N-glycosylation': 'N[^P][CV]',    # https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4721579/
        # 'O-glycosylation': ''
    }
})


def has_motif(site_sequence: str, motif: Pattern):
    print(motif.search(site_sequence))
    return motif.search(site_sequence) is not None


def mutate_sequence(site: Site, mutation: Mutation, offset: int) -> str:
    relative_position = mutation.position - site.position + offset
    sequence = site.get_nearby_sequence(offset)

    assert sequence[relative_position] == mutation.ref

    sequence = sequence[:relative_position] + mutation.alt + sequence[relative_position + 1:]

    return sequence


MotifsRelatedCounts = namedtuple(
    'MotifsRelatedCounts',
    [
        'sites_with_motif', 'sites_with_broken_motif',
        'muts_around_sites_with_motif', 'muts_breaking_sites_motif'
    ]
)


def count_muts_and_sites(mutations_query, site_type: SiteType, motifs_db=all_motifs) -> MotifsRelatedCounts:
    mutations_affecting_sites = mutations_query.filter(
        Mutation.affected_sites.any(Site.type.contains(site_type))
    )

    ptm_muts = mutations_affecting_sites.count()

    muts_around_sites_with_motif = 0
    muts_breaking_sites_motif = 0

    sites_with_motif = defaultdict(set)
    sites_with_broken_motif = defaultdict(set)

    site_specific_motifs = motifs_db[site_type.name]

    for site in Site.query.filter(Site.type.contains(site_type)):
        for motif_name, motif in site_specific_motifs.items():
            if has_motif(site.sequence, motif):
                sites_with_motif[motif_name].add(site)

    for mutation in tqdm(mutations_affecting_sites, total=ptm_muts):
        sites = mutation.affected_sites

        for site in sites:

            for motif_name, motif in site_specific_motifs.items():
                if site in sites_with_motif[motif_name]:
                    muts_around_sites_with_motif += 1

                    mutated_sequence = mutate_sequence(site, mutation, offset=7)

                    if not has_motif(mutated_sequence, motif):
                        sites_with_broken_motif[motif_name].add(site)
                        muts_breaking_sites_motif += 1

    return MotifsRelatedCounts(
        sites_with_motif=sites_with_motif,
        sites_with_broken_motif=sites_with_broken_motif,
        muts_around_sites_with_motif=muts_around_sites_with_motif,
        muts_breaking_sites_motif=muts_breaking_sites_motif
    )

