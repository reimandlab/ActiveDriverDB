import re
from collections import defaultdict, ChainMap
from typing import Iterable, Mapping, Union, List, NamedTuple

from flask_sqlalchemy import BaseQuery
from tqdm import tqdm

from analyses.active_driver import ActiveDriverResult
from models import Site, SiteType, Mutation, MutationSource, Protein, Gene, and_, or_, SiteMotif


def motifs_for_site_type(site_type_name: str):
    motifs_by_site_type = SiteMotif.query.filter(
        SiteMotif.site_type.has(SiteMotif.name == site_type_name)
    )
    return {
        motif.name: motif.expression
        for motif in motifs_by_site_type
    }


def get_motifs_hierarchy():

    motifs_hierarchy = {
        'glycosylation': {
            'N-linked': motifs_for_site_type('N-glycosylation'),
            'O-linked': motifs_for_site_type('O-glycosylation'),
            'C-linked': motifs_for_site_type('C-glycosylation')
        }
    }
    return motifs_hierarchy


def get_all_motifs():

    motifs_hierarchy = get_motifs_hierarchy()

    return {
        site_type: dict(ChainMap(*motif_groups.values()))
        for site_type, motif_groups in motifs_hierarchy.items()
    }


def has_motif(site_sequence: str, motif: str) -> bool:
    return re.search(motif, site_sequence) is not None


def mutate_sequence(site: Site, mutation: Mutation, offset: int) -> str:
    relative_position = mutation.position - site.position + offset
    sequence = site.get_nearby_sequence(offset)

    assert sequence[relative_position] == mutation.ref

    sequence = sequence[:relative_position] + mutation.alt + sequence[relative_position + 1:]

    return sequence


MotifName = str


class MotifsRelatedCounts(NamedTuple):
    sites_with_motif: Mapping[MotifName, int]
    sites_with_broken_motif: Mapping[MotifName, int]
    muts_around_sites_with_motif: Mapping[MotifName, int]
    muts_breaking_sites_motif: Mapping[MotifName, int]


class MotifsData(NamedTuple):
    sites_with_motif: Mapping[MotifName, set]
    sites_with_broken_motif: Mapping[MotifName, set]
    muts_around_sites_with_motif: Mapping[MotifName, Mapping[Mutation, int]]
    muts_breaking_sites_motif: Mapping[MotifName, Mapping[Mutation, int]]


def select_sites_with_motifs(sites: Iterable, motifs) -> Mapping[MotifName, set]:

    sites_with_motif = defaultdict(set)

    for site in sites:
        for motif_name, motif in motifs.items():
            if has_motif(site.sequence, motif):
                sites_with_motif[motif_name].add(site)

    return sites_with_motif


class NoKnownMotifs(Exception):
    pass


class MotifsCounter:

    def __init__(self, site_type: SiteType, mode='broken_motif', motifs_db=get_all_motifs):
        self.site_type = site_type
        self.motifs_db = motifs_db() if callable(motifs_db) else motifs_db
        self.mode = mode

        try:
            self.site_specific_motifs = self.motifs_db[site_type.name]
        except KeyError:
            raise NoKnownMotifs(f'No known motifs for {site_type} in {motifs_db}')

        self.breaking_modes = {
            'change_of_motif': self.change_of_motif,
            'broken_motif': self.broken_motif
        }

    @staticmethod
    def change_of_motif(mutated_seq, motif):
        return not has_motif(mutated_seq, motif)

    def broken_motif(self, mutated_seq, _):
        return not any(
            has_motif(mutated_seq, motif) for motif in self.site_specific_motifs.values()
        )

    def gather_muts_and_sites(
        self, mutations: BaseQuery, sites: BaseQuery,
        show_progress=True, occurrences_in: List[MutationSource] = None, intersection=None
    ) -> MotifsData:
        """If occurrences_in is provided, the count of mutations will
        represent number of occurrences of mutations in provided
        sources, instead of number of distinct substitutions.
        """

        if intersection:
            accepted_sites = sites.join(Mutation.affected_sites).filter(and_(
                *[Mutation.in_sources(source) for source in intersection]
            )).all()
        else:
            accepted_sites = sites.all()

        mutations_affecting_sites = mutations.filter(
            Mutation.affected_sites.any(Site.types.contains(self.site_type))
        )

        muts_around_sites_with_motif = defaultdict(dict)
        muts_breaking_sites_motif = defaultdict(dict)

        sites_with_broken_motif = defaultdict(set)

        sites_with_motif = select_sites_with_motifs(accepted_sites, self.site_specific_motifs)

        if occurrences_in:
            def mutation_count(mut: Mutation):
                return sum([
                    mut.sources_map[source.name].get_value() if source.name in mut.sources_map else 0
                    for source in occurrences_in
                ])
        else:
            def mutation_count(mut):
                return 1

        is_affected = self.breaking_modes[self.mode]

        if show_progress:
            ptm_muts = mutations_affecting_sites.count()
            mutations_affecting_sites = tqdm(mutations_affecting_sites, total=ptm_muts)

        for mutation in mutations_affecting_sites:
            sites = mutation.affected_sites

            for site in sites:
                if site not in accepted_sites:
                    continue

                for motif_name, motif in self.site_specific_motifs.items():
                    if site in sites_with_motif[motif_name]:
                        count = mutation_count(mutation)
                        muts_around_sites_with_motif[motif_name][mutation] = count

                        mutated_sequence = mutate_sequence(site, mutation, offset=7)

                        if is_affected(mutated_sequence, motif):
                            sites_with_broken_motif[motif_name].add(site)
                            muts_breaking_sites_motif[motif_name][mutation] = count

        return MotifsData(
            sites_with_motif=sites_with_motif,
            sites_with_broken_motif=sites_with_broken_motif,
            muts_around_sites_with_motif=muts_around_sites_with_motif,
            muts_breaking_sites_motif=muts_breaking_sites_motif
        )

    def count_muts_and_sites(self, *args, **kwargs) -> MotifsRelatedCounts:

        data = self.gather_muts_and_sites(*args, **kwargs)

        return MotifsRelatedCounts(
            sites_with_motif=defaultdict(int, {
                motif: len(sites)
                for motif, sites in data.sites_with_motif.items()
            }),
            sites_with_broken_motif=defaultdict(int, {
                motif: len(sites)
                for motif, sites in data.sites_with_broken_motif.items()
            }),
            muts_around_sites_with_motif=defaultdict(int, {
                motif: sum(counts_by_mutations.values())
                for motif, counts_by_mutations in data.muts_around_sites_with_motif.items()
            }),
            muts_breaking_sites_motif=defaultdict(int, {
                motif: sum(counts_by_mutations.values())
                for motif, counts_by_mutations in data.muts_breaking_sites_motif.items()
            })
        )


def count_by_sources(
    sources: List[MutationSource], site_type: SiteType, primary_isoforms=True,
    by_genes=True, genes=None, muts_conjunction=or_, **kwargs
):

    base_query = Mutation.query.filter(muts_conjunction(
        *[Mutation.in_sources(source) for source in sources]
    ))

    if primary_isoforms:
        base_query = base_query.join(Protein).filter(Protein.is_preferred_isoform)

    sites = Site.query.filter(Site.types.contains(site_type))

    counter = MotifsCounter(site_type)

    if not by_genes:
        return counter.count_muts_and_sites(base_query, sites,  **kwargs)

    counts_by_genes = {}

    if not genes:
        genes = Gene.query.all()

    for gene in tqdm(genes):

        query = base_query.filter(Mutation.protein == gene.preferred_isoform)
        gene_sites = sites.filter(Site.protein == gene.preferred_isoform)
        counts_by_genes[gene.name] = counter.count_muts_and_sites(
            query, gene_sites, show_progress=False, **kwargs
        )

    return counts_by_genes


def count_by_active_driver(
    site_type: SiteType, source: MutationSource,
    result: ActiveDriverResult, by_genes=False, **kwargs
) -> Union[MotifsRelatedCounts, Mapping[str, MotifsRelatedCounts]]:

    genes_passing_threshold = Gene.query.filter(Gene.name.in_(result['top_fdr'].gene.values)).all()

    return count_by_sources(
        [source], site_type, by_genes=by_genes, genes=genes_passing_threshold, **kwargs
    )
