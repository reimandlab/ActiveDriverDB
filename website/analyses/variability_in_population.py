from numpy import percentile
from rpy2.robjects import FloatVector, r
from sqlalchemy import func, distinct, case, literal_column
from tqdm import tqdm

from database import db
from helpers.cache import cache_decorator, Cache
from models import Mutation, Protein, Site, ExomeSequencingMutation, The1000GenomesMutation, and_

cached = cache_decorator(Cache('.variability_cache'))
population_sources = [ExomeSequencingMutation, The1000GenomesMutation]
wilcox = r['wilcox.test']


def variability_in_population(
    source, site_type=None, protein_subset=None, rare_threshold=0.5,
    only_primary=True, site_motif=None
):

    all_muts = func.count(distinct(Mutation.id)).label('muts_cnt')

    query = (
        db.session.query(
            func.count(distinct(case(
                [
                    (
                        source.maf_all <= rare_threshold / source.scale,
                        Mutation.id
                    )
                ],
                else_=literal_column('NULL')
            ))) * 100 / all_muts, all_muts
        ).select_from(source).join(Mutation).join(Protein)
    )

    if only_primary:
        query = query.filter(Protein.is_preferred_isoform)

    if site_type is None:
        query = query.filter(~Mutation.affected_sites.any())
    else:
        site_condition = Site.types.contains(site_type)

        if site_motif:
            site_condition = and_(
                site_condition,
                Site.has_motif(site_motif)
            )

        query = query.filter(Mutation.affected_sites.any(site_condition))

    if protein_subset:
        query = query.filter(Protein.id.in_(protein_subset))

    return query


def proteins_variability(source, only_primary=True, site_type=None, without_sites=False, by_counts=False, site_motif=None):

    if by_counts:
        variability_measure = func.count(distinct(source.id))
    else:
        variability_measure = func.sum(source.maf_all)

    query = (
        db.session.query(
            Protein.id,
            variability_measure / func.length(Protein.sequence)
        ).select_from(source).join(Mutation).join(Protein)
    )

    if only_primary:
        query = query.filter(Protein.is_preferred_isoform)

    if site_type is not None:
        assert not without_sites

        site_condition = Site.types.contains(site_type)
        if site_motif:
            site_condition = and_(
                site_condition,
                Site.has_motif(site_motif)
            )

        query = query.filter(Protein.sites.any(site_condition))

    if site_motif is not None:
        assert site_type

    if without_sites:
        query = query.filter(~Protein.sites.any())

    query = query.group_by(Protein.id)

    return query


def group_by_substitution_rates(source, only_primary=True, bins_count=100, by_frequency=False, site_type=None):
    # see http://journals.plos.org/plosgenetics/article?id=10.1371/journal.pgen.1004919#sec004:
    # "Global variation of PTM regions", though this operates only on mis-sense aminoacid substitutions
    # (non-sense and synonymous mutations are not considered)
    percentiles_per_bin = 100 / bins_count

    protein_rates = proteins_variability(source, only_primary, by_counts=not by_frequency, site_type=site_type).all()

    substitution_rates = [float(rate) for protein, rate in protein_rates]

    bins = []

    previous_median = 0

    for i in range(1, bins_count + 1):
        bin_median = percentile(substitution_rates, i * percentiles_per_bin)

        bin_proteins = [
            protein
            for protein, rate in protein_rates
            if previous_median < rate <= bin_median
        ]
        bins.append(bin_proteins)

        previous_median = bin_median

    return bins


def variability_vector(result, source):
    return FloatVector(result[source.name])


@cached
def ptm_variability_population_rare_substitutions(site_type, motif=None):
    """Compare variability of sequence in PTM sites
    with the variability of sequence outside of PTM sites,
    using frequency of rare substitutions.
    """
    results = {}

    protein_bins = {}

    print(f'Rare substitutions in PTM/non-PTM regions for: {site_type}')

    for population_source in population_sources:
        protein_bins[population_source] = group_by_substitution_rates(population_source)

    for group, site_type in [('non-PTM', None), ('PTM regions', site_type)]:

        group_muts = []
        result = {}

        for population_source in population_sources:

            variability = []
            source_group_muts = []

            for protein_bin in tqdm(protein_bins[population_source]):

                for percentage, muts_count in variability_in_population(
                    population_source, site_type,
                    protein_subset=protein_bin,
                    site_motif=motif
                ):
                    if muts_count == 0:
                        percentage = 0
                    variability.append(float(percentage))
                    source_group_muts.append(muts_count)

            result[population_source.name] = variability
            group_muts += source_group_muts

        print(f'Total muts in {group}: {sum(group_muts)}')

        results[group] = result

    return results


def does_median_differ_significances(results, paired=False):
    significances = {}

    for population_source in population_sources:
        visibilities = [
            variability_vector(result, population_source)
            for result in results.values()
        ]
        significance = wilcox(*visibilities, paired=paired)
        significances[population_source.name] = significance.rx("p.value")[0][0]

    return significances


@cached
def proteins_variability_by_ptm_presence(site_type, by_counts, site_motif=None):
    results = {}

    for group, without_ptm, site_type in [('Without PTM sites', True, None), ('With PTM sites', False, site_type)]:
        result = {}
        counts = {}

        for population_source in population_sources:

            rates = proteins_variability(
                population_source, site_type=site_type, without_sites=without_ptm, by_counts=by_counts,
                site_motif=(site_motif if site_type else None)
            )
            proteins, variability = zip(*rates)

            result[population_source.name] = variability
            counts[population_source.name] = len(proteins)

        print(f'Proteins distribution for {group} (site_type: {site_type}): {counts}')

        results[group] = result

    return results
