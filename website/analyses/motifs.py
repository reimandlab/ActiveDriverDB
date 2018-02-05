import re
from collections import defaultdict, namedtuple
from typing import Pattern, Iterable, Mapping, Union

from flask_sqlalchemy import BaseQuery
from tqdm import tqdm

from analyses.active_driver import ActiveDriverResult
from models import Site, SiteType, Mutation, MutationSource, Protein


def compile_motifs(motifs: dict):
    for key, value in motifs.items():
        if isinstance(value, dict):
            motifs[key] = compile_motifs(value)
        else:
            motifs[key] = re.compile(value)
    return motifs


raw_motifs = {
    'glycosylation': {
        # Sequons:
        'N-glycosylation': '.{7}N[^P][ST].{5}',     # https://prosite.expasy.org/PDOC00001
        'Atypical N-glycosylation': '.{7}N[^P][CV].{5}',    # https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4721579/

        # Based on https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1301293/
        'O-glycosylation TAPP': '.{7}TAPP',
        'O-glycosylation TSAP': '.{7}TSAP',
        'O-glycosylation TV.P': '.{7}TV.P',
        'O-glycosylation [ST]P.P': '.{7}[ST]P.P',

        # https://www.uniprot.org/help/carbohyd
        'C-linked W..W': '(.{7}W..W.{4}|.{4}W..W.{7})',
        'C-linked W[ST].C': '.{7}W[ST].C.{4}',
    }
}

all_motifs = compile_motifs(raw_motifs)


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


def count_muts_and_sites_from_query(
    mutations: BaseQuery, site_type: SiteType, motifs_db=all_motifs
) -> MotifsRelatedCounts:

    mutations_affecting_sites = mutations.filter(
        Mutation.affected_sites.any(Site.type.contains(site_type))
    )
    ptm_muts = mutations_affecting_sites.count()
    sites = Site.query.filter(Site.type.contains(site_type))

    return count(mutations_affecting_sites, ptm_muts, sites, site_type, motifs_db)


def count_muts_and_sites(
    mutations: Iterable, sites: Iterable, site_type: SiteType, motifs_db=all_motifs, **kwargs
) -> MotifsRelatedCounts:

    ptm_muts = len(mutations) if isinstance(mutations, list) else None

    return count(mutations, ptm_muts, sites, site_type, motifs_db, **kwargs)


def count(mutations_affecting_sites, ptm_muts, sites, site_type, motifs_db, mode='change_of_motif') -> MotifsRelatedCounts:

    muts_around_sites_with_motif = defaultdict(int)
    muts_breaking_sites_motif = defaultdict(int)

    sites_with_broken_motif = defaultdict(set)

    site_specific_motifs = motifs_db[site_type.name]
    sites_with_motif = select_sites_with_motifs(sites, site_specific_motifs)

    def change_of_motif(mutated_seq, motif):
        return not has_motif(mutated_seq, motif)

    def broken_motif(mutated_seq, _):
        return not any(has_motif(mutated_seq, motif) for motif in site_specific_motifs.values())

    breaking_modes = {
        'change_of_motif': change_of_motif,
        'broken_motif': broken_motif
    }

    is_affected = breaking_modes[mode]

    for mutation in tqdm(mutations_affecting_sites, total=ptm_muts):
        sites = mutation.affected_sites

        for site in sites:

            for motif_name, motif in site_specific_motifs.items():
                if site in sites_with_motif[motif_name]:
                    muts_around_sites_with_motif[motif_name] += 1

                    mutated_sequence = mutate_sequence(site, mutation, offset=7)

                    if is_affected(mutated_sequence, motif):
                        sites_with_broken_motif[motif_name].add(site)
                        muts_breaking_sites_motif[motif_name] += 1

    return MotifsRelatedCounts(
        sites_with_motif=sites_with_motif,
        sites_with_broken_motif=sites_with_broken_motif,
        muts_around_sites_with_motif=muts_around_sites_with_motif,
        muts_breaking_sites_motif=muts_breaking_sites_motif
    )


def count_by_source(source: MutationSource, site_type: SiteType, primary_isoforms=True):

    query = Mutation.query.filter(Mutation.in_sources(source))

    if primary_isoforms:
        query = query.filter(Mutation.protein.is_preferred_isoform)

    return count_muts_and_sites_from_query(query, site_type)


def count_by_active_driver(
    site_type: SiteType, result: ActiveDriverResult, by_genes=False, **kwargs
) -> Union[MotifsRelatedCounts, Mapping[str, MotifsRelatedCounts]]:

    active_mutations = result['all_active_mutations']
    active_sites = result['all_active_sites']

    genes_passing_threshold = result['top_fdr'].gene.values

    mutations = []
    sites = []
    gene_protein = {}
    counts_by_genes = {}

    for gene_name, group in tqdm(active_mutations.groupby('gene')):

        if gene_name not in genes_passing_threshold:
            continue

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
            counts_by_genes[gene_name] = count_muts_and_sites(gene_mutations, gene_sites, site_type, **kwargs)
        else:
            mutations.extend(gene_mutations)
            sites.extend(gene_sites)

    if by_genes:
        return counts_by_genes
    else:
        return count_muts_and_sites(mutations, sites, site_type, **kwargs)
