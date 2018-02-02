import re
from collections import defaultdict, namedtuple
from typing import Pattern, Iterable, Mapping

from flask_sqlalchemy import BaseQuery
from tqdm import tqdm

from analyses import active_driver
from analyses.active_driver import ActiveDriverResult
from models import Site, SiteType, Mutation, InheritedMutation, MC3Mutation, MutationDetails, MutationSource, Protein


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


def has_motif(site_sequence: str, motif: Pattern) -> bool:
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


def select_sites_with_motifs(sites: Iterable, motifs) -> Mapping[str, set]:

    sites_with_motif = defaultdict(set)

    for site in sites:
        for motif_name, motif in motifs.items():
            if has_motif(site.sequence, motif):
                sites_with_motif[motif_name].add(site)

    return sites_with_motif


def count_muts_and_sites_from_query(mutations: BaseQuery, site_type: SiteType, motifs_db=all_motifs) -> MotifsRelatedCounts:

    mutations_affecting_sites = mutations.filter(
        Mutation.affected_sites.any(Site.type.contains(site_type))
    )
    ptm_muts = mutations_affecting_sites.count()
    sites = Site.query.filter(Site.type.contains(site_type))

    return count(mutations_affecting_sites, ptm_muts, sites, site_type, motifs_db)


def count_muts_and_sites(mutations: Iterable, sites: Iterable, site_type: SiteType, motifs_db=all_motifs) -> MotifsRelatedCounts:

    ptm_muts = len(mutations) if isinstance(mutations, list) else None

    return count(mutations, ptm_muts, sites, site_type, motifs_db)


def count(mutations_affecting_sites, ptm_muts, sites, site_type, motifs_db) -> MotifsRelatedCounts:

    muts_around_sites_with_motif = 0
    muts_breaking_sites_motif = 0

    sites_with_broken_motif = defaultdict(set)

    site_specific_motifs = motifs_db[site_type.name]
    sites_with_motif = select_sites_with_motifs(sites, site_specific_motifs)

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


def count_by_source(source: MutationSource, site_type: SiteType):

    return count_muts_and_sites_from_query(
        Mutation.query.filter(Mutation.in_sources(source)),
        site_type
    )


def count_by_active_driver(site_type: SiteType, result: ActiveDriverResult, by_genes=False):

    active_mutations = result['all_active_mutations']
    active_sites = result['all_active_sites']

    mutations = []
    sites = []
    gene_protein = {}

    for gene_name, group in tqdm(active_mutations.groupby('gene')):
        gene_mutations = []

        if gene_name not in gene_protein:
            gene_protein[gene_name] = (
                Protein.query
                .filter(Protein.is_preferred_isoform)
                .filter(Protein.gene_name == gene_name)
                .one()
            )

        protein = gene_protein[gene_name]

        for data in group.itertuples(index=False):

            assert protein.refseq == data.isoform

            mutation = (
                Mutation.query
                .filter(Mutation.protein == protein)
                .filter_by(
                    position=data.position,
                    alt=data.mut_residue
                ).one()
            )

            assert mutation.alt == data.mut_residue

            gene_mutations.append(mutation)

        gene_sites = [
            Site.query.filter_by(protein=gene_protein[s.gene], position=s.position).one()
            for s in active_sites.query('gene == @gene_name').itertuples(index=False)
        ]

        if by_genes:
            print(gene_name, count_muts_and_sites(gene_mutations, gene_sites, site_type))
        else:
            mutations.extend(gene_mutations)
            sites.extend(gene_sites)

    if not by_genes:
        return count_muts_and_sites(mutations, sites, site_type)


ad_analyses = [
    active_driver.clinvar_analysis,
    active_driver.pan_cancer_analysis
]


def motifs_in_active_driver(site_type: SiteType):
    for analyses in ad_analyses:
        for analysis in analyses:
            result = analysis(site_type.name)
            counts = count_by_active_driver(site_type, result, by_genes=True)
            print(analysis, counts)
