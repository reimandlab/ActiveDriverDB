from collections import defaultdict
from typing import List
from warnings import warn

from tqdm import tqdm

from analyses.motifs import MotifsCounter, NoKnownMotifs
from helpers.plots import pie_chart
from models import MutationSource, SiteType, Site, Protein, Mutation, Gene, InheritedMutation, MC3Mutation
from database import db

from ..store import cases
from .common import site_types


def gather_ptm_muts_impacts(
    source: MutationSource,
    site_type: SiteType,
    limit_to_genes: List[str]=None,
    occurrences=True,
    limit_to_muts=False,
    muts_filter=None
):
    """

    Args:
        source: mutation source to gather mutations from
        site_type: PTM site type for which affecting mutations will be gathered
        limit_to_genes: list of gene names for which mutations of primary isoforms will be gathered
        occurrences: whether to count occurrences or distinct mutations
        limit_to_muts: list of tuples defining mutations and counts, like from AD data frame
            providing custom mutations lists overrides "occurrences" setting
        muts_filter: SQLAlchemy filter for mutations
    """

    try:
        motifs_counter = MotifsCounter(site_type, mode='change_of_motif')
    except NoKnownMotifs as error:
        warn(f'Impacts collection failed, due to: {error}')
        return {}

    sites = (
        Site.query.filter(SiteType.fuzzy_filter(site_type, join=True))
        .join(Protein).filter(Protein.is_preferred_isoform)
    )

    def fuzzy_site_filter(sites):
        return [
            site for site in sites
            # matches 'O-glycosylation' for site_type 'glycosylation'
            if any(site_type.name in type_name for type_name in site.types_names)
        ]

    mutations_by_impact_by_gene = {
        # order matters
        'direct': defaultdict(int),
        'motif-changing': defaultdict(int),
        'proximal': defaultdict(int),
        'distal': defaultdict(int)
    }

    mutations = (
        Mutation.query
        .filter(Mutation.in_sources(source))
        .join(Protein)
        .join(Gene, Gene.preferred_isoform_id == Protein.id)
    )
    if muts_filter is not None:
        mutations = mutations.filter(muts_filter)

    motifs_data = motifs_counter.gather_muts_and_sites(mutations, sites, occurrences_in=[source])

    all_breaking_muts = set()
    for motif_name, breaking_muts in motifs_data.muts_breaking_sites_motif.items():
        all_breaking_muts.update(breaking_muts)

    mutations = mutations.filter(Mutation.affected_sites.any(SiteType.fuzzy_filter(site_type, join=True)))
    if limit_to_genes is not None:
        proteins_ids = (
            db.session.query(Protein.id)
            .select_from(Gene)
            .join(Gene.preferred_isoform)
            .filter(Gene.name.in_(limit_to_genes))
            .all()
        )
        mutations = mutations.filter(
            Protein.id.in_(proteins_ids)
        )

    mutations = mutations.with_entities(Gene.name, Mutation)

    if limit_to_muts is not False:
        muts = {
            Mutation.query.filter_by(
                position=mut.position,
                alt=mut.mut_residue,
                protein=Protein.query.filter_by(refseq=mut.isoform).one()
            ).one(): int(mut.count)
            for mut in limit_to_muts.itertuples(index=False)
        }

    for gene_name, mutation in tqdm(mutations, total=mutations.count()):

        if limit_to_muts is not False:
            if mutation not in muts:
                continue
            value = muts[mutation]
        else:
            value = mutation.sources_map[source.name].get_value() if occurrences else 1

        impact = mutation.impact_on_ptm(fuzzy_site_filter)
        if impact != 'direct' and mutation in all_breaking_muts:
            mutations_by_impact_by_gene['motif-changing'][gene_name] += value
            continue
        assert impact != 'none'
        mutations_by_impact_by_gene[impact][gene_name] += value

    return mutations_by_impact_by_gene


impact_cases = cases(source=[InheritedMutation, MC3Mutation], site_type=site_types).set_mode('product')


@cases(site_type=site_types)
@pie_chart
def by_impact_clinvar_strict(site_type: SiteType):
    from models import source_manager

    muts_by_impact_by_gene = gather_ptm_muts_impacts(
        InheritedMutation, site_type,
        muts_filter=(
            source_manager.get_relationship(InheritedMutation).has(
                InheritedMutation.significance_filter('strict')
            )
        )
    )

    muts_by_impact = {
        impact: sum(gene_muts.values())
        for impact, gene_muts in muts_by_impact_by_gene.items()
    }

    return {InheritedMutation.name: muts_by_impact}


@impact_cases
@pie_chart
def by_impact(source: MutationSource, site_type: SiteType):

    muts_by_impact_by_gene = gather_ptm_muts_impacts(source, site_type)

    muts_by_impact = {
        impact: sum(gene_muts.values())
        for impact, gene_muts in muts_by_impact_by_gene.items()
    }

    return {source.name: muts_by_impact}
