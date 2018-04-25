import operator
import random
from collections import namedtuple, Counter, defaultdict
from functools import reduce, partial
from statistics import median
from typing import List

from numpy import NaN
from sqlalchemy import and_, func, distinct, desc
from sqlalchemy.orm import aliased
from tqdm import tqdm
from scipy.stats import fisher_exact, chisquare

from database import join_unique, db, fast_count
from models import (
    Protein, Mutation, The1000GenomesMutation, MC3Mutation, InheritedMutation, Gene, Site,
    MutationSource, source_manager,
    SiteType,
)


def count_mutated_potential_sites():
    count = 0
    total_length = 0
    for protein in tqdm(Protein.query, total=Protein.query.count()):
        mutated_positions = set()
        for mut in protein.confirmed_mutations:
            mutated_positions.update(range(mut.position - 7, mut.position + 7))
        total_length += protein.length

        for i in range(protein.length):
            if i in mutated_positions:
                count += 1
    print(count, total_length, count/total_length*100)


def test_enrichment_of_ptm_mutations_among_mutations_subset(subset_query, reference_query, iterations_count=100000, subset_size=None, subset_ptms=None):
    """Perform tests according to proposed algorithm:

    1. Count the number of all ClinVar mutations as C, PTM-associated ClinVar mutations as D=27071
        and percentage of the latter as E=19%.
    2. Randomly draw C mutations from 1,000 Genomes
    3. Record the number and % of those N mutations that affect PTM sites, as P, Q
    4. Repeat 2-3 for M=10,000 times
    5. Count in how many of M iterations does D>P and E>Q. These percentages make up the permutation test p-values
    6. Repeat with TCGA instead of ClinVar.


    Args:
        subset_query:
            SQLAlchemy query yielding mutation dataset
            to test (e.g. ClinVar or TCGA)

        reference_query:
            query yielding a population dataset to test
            against (to be used as a reference distribution
            e.g. 1000 Genomes)

    Returns:
        namedtuple with:
            median,
            median percentage,
            p_value: 1 - p-value,
            enriched_ptm_muts_in_iterations: list of counts of PTM sites discovered in each of sampling iterations,
            expected_ptm_muts:  expected number of mutations associated with PTM sites
    """
    ptm_enriched_absolute = 0
    ptm_enriched_percentage = 0

    is_ptm = Mutation.precomputed_is_ptm

    # 1.
    if subset_query:
        all_mutations = subset_query.count()                        # C
        ptm_mutations = subset_query.filter(is_ptm).count()         # D
    else:
        assert subset_size and subset_ptms
        all_mutations = subset_size
        ptm_mutations = subset_ptms

    ptm_percentage = ptm_mutations / all_mutations * 100        # E

    print('Counting enrichment in random subsets of background.')
    print('All: %s, PTM: %s, %%: %s' % (all_mutations, ptm_mutations, ptm_percentage))

    all_reference_mutations = reference_query.all()

    enriched_ptms = []
    enriched_percentage = []

    # 4.
    for _ in tqdm(range(iterations_count)):
        # 2.
        random_reference = random.sample(all_reference_mutations, all_mutations)

        # 3.
        all_in_iteration = len(random_reference)
        ptm_in_iteration = sum(1 for mutation in random_reference if mutation.precomputed_is_ptm)  # P
        iteration_percentage = ptm_in_iteration / all_in_iteration * 100                           # Q

        assert all_in_iteration == all_mutations

        # 5.
        if ptm_mutations > ptm_in_iteration:        # D > P
            ptm_enriched_absolute += 1
        if ptm_percentage > iteration_percentage:   # E > Q
            ptm_enriched_percentage += 1

        enriched_ptms.append(ptm_in_iteration)
        enriched_percentage.append(iteration_percentage)

    median_ptms = median(enriched_ptms)
    median_percentage = median(enriched_percentage)

    result_tuple = namedtuple(
        'EnrichmentAnalysisResult',
        'enriched_ptm_muts_in_iterations, '
        'median, median_percentage, '
        'p_value, p_value_percentage, '
        'observed_ptm_muts'
    )

    return result_tuple(
        enriched_ptms,
        median_ptms,
        median_percentage,
        ptm_enriched_absolute / iterations_count,
        ptm_enriched_percentage / iterations_count,
        ptm_mutations
    )


def get_confirmed_mutations(
        sources, only_preferred=True, genes=None, confirmed_by_definition=False,
        base_query=None
    ):
    """
    Utility to generate a query for retrieving confirmed mutations having specific mutation details.

    Args:
        sources: list of mutation details (sources) to be used to filter
            the mutations (including sources with non-confirmed mutations)
        only_preferred: include only mutations from preferred isoforms
        genes: limit to genes from provided list
        confirmed_by_definition: do not apply the expensive is_confirmed=True
            filter as all sources include only confirmed mutations
        base_query: the initial mutation query (allows to adjust selected columns)

    Returns:
        Query object yielding mutations.
    """

    if not base_query:
        base_query = Mutation.query

    mutations = base_query

    def only_from_primary_isoforms(mutations_query):

        mutations_query = join_unique(mutations_query, Protein)
        return mutations_query.filter(Protein.is_preferred_isoform)

    if not confirmed_by_definition:
        mutations = mutations.filter_by(is_confirmed=True)

    # TODO: remove?
    mutations = only_from_primary_isoforms(mutations)

    if genes:
        mutations = mutations.filter(Protein.id.in_([g.preferred_isoform_id for g in genes]))

    selected_mutations = mutations.filter(Mutation.in_sources(*sources))

    if only_preferred:
        selected_mutations = only_from_primary_isoforms(selected_mutations)

    return selected_mutations


def test_ptm_enrichment():
    # 1000 Genomes
    ref_genes = get_genes_with_mutations_from_sources([The1000GenomesMutation], only_genes_with_ptm_sites=True)

    # TCGA against 1000Genomes
    cancer_genes = load_cancer_census()
    tcga_result = parametric_test_ptm_enrichment(MC3Mutation, The1000GenomesMutation, cancer_genes, ref_genes)

    # ClinVar against 1000Genomes
    tested_genes = get_genes_with_mutations_from_sources([InheritedMutation], only_genes_with_ptm_sites=True)
    clinvar_result = parametric_test_ptm_enrichment(InheritedMutation, The1000GenomesMutation, tested_genes, ref_genes)

    return clinvar_result, tcga_result


def test_enrichment_against_source(ptm_muts_count: int, all_muts_count: int, source=The1000GenomesMutation):
    ref_genes = get_genes_with_mutations_from_sources([source], only_genes_with_ptm_sites=True)
    reference_mutations = get_confirmed_mutations([source], genes=ref_genes)

    result = test_enrichment_of_ptm_mutations_among_mutations_subset(
        None, reference_mutations, subset_size=all_muts_count, subset_ptms=ptm_muts_count
    )

    return result


def parametric_test_ptm_enrichment(tested_source, reference_source, tested_genes, ref_genes):
    """Uses only mutations from primary isoforms."""

    # e.g. 1000Genomes
    reference_mutations = get_confirmed_mutations([reference_source], genes=ref_genes)

    # e.g. ClinVar
    tested_mutations = get_confirmed_mutations([tested_source], genes=tested_genes)

    result = test_enrichment_of_ptm_mutations_among_mutations_subset(tested_mutations, reference_mutations)

    return result


def non_parametric_test_ptm_enrichment():
    """Uses only mutations from primary isoforms.

    Use wilcox.test from R to compare distributions
    of PTM affecting/all mutations between clinvar
    and 1000 Genomes Project mutation datasets.
    """
    from rpy2.robjects import r
    from rpy2.robjects import FloatVector

    def collect_ratios(sources, only_genes_with_ptm_sites=False):
        ratios = []
        genes = get_genes_with_mutations_from_sources(sources, only_genes_with_ptm_sites)

        print('Number of genes:', len(genes))

        for gene in tqdm(genes):
            protein = gene.preferred_isoform
            filters = and_(
                Mutation.protein == protein,
                Mutation.is_confirmed == True
            )
            number_of_all_mutations = Mutation.query.filter(filters).count()
            number_of_ptm_mutations = Mutation.query.filter(and_(
                filters,
                Mutation.precomputed_is_ptm == True
            )).count()
            ratios.append(number_of_ptm_mutations/number_of_all_mutations)
        return FloatVector(ratios)

    results = []
    wilcox = r['wilcox.test']

    for exclude_no_ptms in [True, False]:
        print('Genes with no PTM sites excluded?', exclude_no_ptms)

        ratios_clinvar = collect_ratios([InheritedMutation], exclude_no_ptms)
        ratios_tkgenomes = collect_ratios([The1000GenomesMutation], exclude_no_ptms)

        result = wilcox(ratios_clinvar, ratios_tkgenomes, alternative='greater')
        print('Clinvar / 1000Genomes', result)

        results.append(result)

        ratios_both = collect_ratios([InheritedMutation, The1000GenomesMutation], exclude_no_ptms)
        result = wilcox(ratios_both, ratios_tkgenomes, alternative='greater')
        print('1000Genomes & Clinvar / 100Genomes', result)
        results.append(result)

    return results


def load_cancer_census(cancer_census_path='data/census.csv'):
    """Load genes from cancer census.

    Args:
        cancer_census_path: this file needs to be downloaded from COSMIC
    """
    from pandas import read_csv

    census = read_csv(cancer_census_path)
    gene_names = set(census.gene_symbol)

    cancer_genes = set()

    for name in gene_names:
        g = Gene.query.filter_by(name=name).first()
        if g:
            cancer_genes.add(g)
        else:
            print(f'Cancer Census gene: "{name}" not in database')
    return cancer_genes


def get_genes_with_mutations_from_sources(sources, only_genes_with_ptm_sites=False):
    query = (
        db.session.query(Gene)
        .join(Protein, Gene.preferred_isoform_id == Protein.id)
        .join(Mutation)
    )
    query = query.filter(Mutation.in_sources(*sources))

    genes = set(query.distinct())

    if only_genes_with_ptm_sites:
        return {
            gene
            for gene in genes
            if gene.preferred_isoform.sites
        }
    return genes


def count_mutations_from_genes(genes, sources, only_preferred_isoforms=False, strict=True):
    """Counts mutations and PTM mutations from isoforms from given set of genes.

    Args:
        genes: a list of Gene
        only_preferred_isoforms: should only one isoform per gene
            (the preferred/primary one) be used when filtering mutations?
        sources: a list of MutationDetails - only confirmed mutations from
            sources identified by given MutationDetail classes will be counted
    """
    all_mutations_count = 0
    ptm_mutations_count = 0

    if strict:
        base_query = (
            db.session.query(
                Mutation.position,
                Mutation.alt,
                Protein.id
            )
            .select_from(Mutation)
            .join(Protein)
        )
    else:
        base_query = Mutation.query

    for gene in tqdm(genes):
        if only_preferred_isoforms:
            proteins = [gene.preferred_isoform]
        else:
            proteins = gene.isoforms

        mutations_filters = and_(
            Mutation.protein_id.in_([p.id for p in proteins]),
            Mutation.is_confirmed == True,
            Mutation.in_sources(*sources)
        )

        all_mutations_count += (
            base_query
            .filter(mutations_filters)
            .distinct().count()
        )

        ptm_mutations_count += (
            base_query
            .filter(and_(
                Mutation.precomputed_is_ptm,
                mutations_filters
            )).distinct().count()
        )

    print(
        all_mutations_count,
        ptm_mutations_count,
        ptm_mutations_count / all_mutations_count
    )
    return all_mutations_count, ptm_mutations_count


def disease_muts_affecting_ptm_sites():
    cancer_genes = load_cancer_census()

    clinvar_genes = get_genes_with_mutations_from_sources([InheritedMutation])

    for only_preferred_isoforms in [True, False]:
        print('Only preferred isoforms:', only_preferred_isoforms)
        print('ClinVar/ClinVar')
        count_mutations_from_genes(clinvar_genes, [InheritedMutation], only_preferred_isoforms)
        print('Cancer census/TCGA')
        count_mutations_from_genes(cancer_genes, [MC3Mutation], only_preferred_isoforms)


def prepare_for_summing(sources: List[MutationSource], count_distinct_substitutions=False) -> List:
    """Mutations from various sources can be summed up differently.

    Given list of mutation sources, checks if the mutation sources
    can be summed up (counted together) in a reasonable way.

    It is possible - though not always advisable - to add frequencies
    of different types of population mutations; it is also possible to
    add occurrence counts of ClinVar and TCGA mutations;

    It is assumed that counting population and non-population
    mutations together is not reasonable as summing frequencies
    with counts has no meaning; however, counting (and summing)
    unique occurrences of mutations from incompatible mutation
    sources is possible with `count_distinct_substitutions=True`.

    Returns:
        list of expressions counting mutations from provided sources
    """

    if count_distinct_substitutions:
        counts = [func.count(distinct(source.id)) for source in sources]
    else:
        source = sources[0]

        if hasattr(source, 'count'):
            assert all(hasattr(s, 'count') for s in sources)
            counts = [
                func.sum(source.count)
                for source in sources
            ]
        elif hasattr(source, 'maf_all'):
            assert all(hasattr(s, 'maf_all') for s in sources)
            counts = [
                func.sum(source.maf_all)
                for source in sources
            ]
        else:
            raise Exception(
                f'Undefined behaviour for summing: {source} source,'
                f' which has neither `count` nor `maf_all` defined.'
            )

    return counts


def most_mutated_sites(
    sources: List[MutationSource], site_type: SiteType=None, limit=25, intersection=True,
    exclusive=None, mutation_filter=None
):
    """Sources must have the same value_type (counts/frequencies)"""

    assert not (intersection and exclusive)

    counts = prepare_for_summing(sources)

    query = (
        db.session.query(
            Site,
            *[
                count.label(f'count_{i}')
                for i, count in enumerate(counts)
            ]
        )
        .select_from(Mutation)
    )

    if intersection:
        for source in sources:
            query = query.join(source)
    else:
        for source in sources:
            query = query.outerjoin(source)

        if exclusive:
            query = query.filter(~Mutation.in_sources(*exclusive))

    if mutation_filter is not None:
        query = query.filter(mutation_filter)

    query = (
        query
        .join(Mutation.affected_sites)
        .filter(Site.protein.has(Protein.is_preferred_isoform))
    )

    if site_type:
        query = query.filter(SiteType.fuzzy_filter(site_type, join=True))

    query = (
        query
        .group_by(Site)
        .having(and_(*counts))
    )

    query = query.subquery()

    total_muts_count = reduce(
        operator.add, [
            getattr(query.c, f'count_{i}')
            for i in range(len(counts))
        ]
    )

    total_muts_count = total_muts_count.label('mutations_count')

    query = (
        db.session.query(
            aliased(Site, query),
            total_muts_count,
        )
        .order_by(desc(total_muts_count))
    )

    return query.limit(limit)


def active_driver_genes_enrichment(analysis_result):
    cancer_genes = load_cancer_census()

    observed_genes = {
        Gene.query.filter_by(name=gene_name).one()
        for gene_name in analysis_result['top_fdr'].gene
    }

    observed_from_census = observed_genes.intersection(cancer_genes)
    print(observed_from_census)
    observed_not_in_census = observed_genes - observed_from_census

    all_genes = set(Gene.query)
    not_observed = all_genes - observed_genes

    not_observed_from_census = not_observed.intersection(cancer_genes)
    not_observed_not_in_census = not_observed - not_observed_from_census

    #     x     |  cancer genes from census  |   other (not in census)
    #  glyco    |  observed_from_census      |       observed_not_in_census
    # not glyc? |

    contingency_table = [
        [observed_from_census, observed_not_in_census],
        [not_observed_from_census, not_observed_not_in_census]
    ]
    contingency_table = [[len(x), len(y)] for x, y in contingency_table]
    print(contingency_table)
    oddsratio, pvalue = fisher_exact(contingency_table)

    return oddsratio, pvalue


def breakdown_of_ptm_mutations(gene_names: List[str], source_name: str):
    source = source_manager.source_by_name[source_name]
    proteins = [
        Gene.query.filter_by(name=gene_name).one().preferred_isoform
        for gene_name in gene_names
    ]
    a = 0
    c = Counter()
    for p in proteins:
        meta_data = {
            m: source_manager.get_bound_relationship(m, source)
            for m in p.mutations
        }
        a += sum(meta.count if meta else 0 for meta in meta_data.values())
        ms = defaultdict(set)
        for m in p.mutations.all():
            sites = m.get_affected_ptm_sites()
            for s in sites:
                for t in s.types:
                    ms[t].add(m)
        for t, muts in ms.items():
            for m in muts:
                c[t] += meta_data[m].count if meta_data[m] else 0

    print(f'All mutations: {a}')
    for t, count in c.items():
        print(t, count, count/a)


from helpers.cache import cache_decorator
from diskcache import Cache

cached = cache_decorator(Cache('.enrichment_cache'))


def get_site_filters(exclude=None, glycosylation='together'):
    """Yields (site type name, type filter) tuples.

    Args:
        exclude: site types to exclude
        glycosylation: 'together', 'only' or 'separate'
    """

    for site_type in tqdm(SiteType.query, total=SiteType.query.count()):
        glyco_kind = 'glycosylation' in site_type.name
        type_name = site_type.name

        if glycosylation == 'together':

            if glyco_kind:
                if type_name == 'glycosylation':
                    type_name = 'glycosylation (all subtypes)'
                else:
                    continue

        elif glycosylation == 'only':

            if not glyco_kind:
                continue

            if type_name == 'glycosylation':
                type_name = 'glycosylation (unknown subtype)'

        if exclude and site_type.name in exclude:
            continue

        if glycosylation == 'together':
            site_filter = SiteType.fuzzy_filter(site_type, join=True)
        else:
            site_filter = Site.types.contains(site_type)

        yield type_name, site_filter


@cached
def sites_mutated_ratio_by_type(source_name: str, disordered=None, display=True, relative=True, **kwargs):
    """What proportion of sites of given type has mutations from given source?

    Args:
        source_name: name of the source (e.g. "ClinVar" or "MC3")
        disordered: filter sites by position with regard to disorder regions:
            None: do not filter - use all sites (default),
            True: only sites in disordered regions,
            False: only sites outside of the disordered regions
        display: should the results be printed out?
        **kwargs: site filter arguments

    Returns: fraction (as percent) of sites that are affected by mutations from given source.

    """
    from stats.table import count_mutated_sites

    source = source_manager.source_by_name[source_name]
    ratios = {}

    for type_name, site_filter in get_site_filters(**kwargs):

        sites = Site.query.filter(site_filter)
        if disordered is not None and relative:
            sites = sites.filter_by(in_disordered_region=disordered).join(Protein)
        mutated = count_mutated_sites(custom_filter=site_filter, model=source, only_primary=True, disordered=disordered)
        sites_count = sites.count()
        print(type_name, sites_count)
        ratios[type_name] = mutated / sites_count * 100 if sites_count else NaN

    if display:
        for type_name, percentage in ratios.items():
            print(f'{type_name}: {percentage:.2f}%')

    return ratios


def are_glycosylation_sites_mutated_more_often(source_name: str, disordered=None, alternative='greater'):
    from stats.table import count_mutated_sites

    glycosylation = SiteType.query.filter_by(name='glycosylation').one()
    non_glycosylation = SiteType.query.filter(~SiteType.name.contains('glycosylation')).all()

    print(f'Comparing {glycosylation} against {non_glycosylation}')

    source = source_manager.source_by_name[source_name]

    count = partial(count_mutated_sites, model=source, only_primary=True, disordered=disordered)

    glyco_filter = SiteType.fuzzy_filter(glycosylation, join=True)
    non_glyco_filter = Site.types.any(SiteType.id.in_([site_type.id for site_type in non_glycosylation]))

    mutated_glycosylation = count(custom_filter=glyco_filter)
    mutated_non_glycosylation = count(custom_filter=non_glyco_filter)

    total_glycosylation = Site.query.filter(glyco_filter).count()
    total_non_glycosylation = Site.query.filter(non_glyco_filter).count()

    #         mutated | not_mutated
    #  glyc |
    # other |

    contingency_table = [
        [mutated_glycosylation, total_glycosylation - mutated_glycosylation],
        [mutated_non_glycosylation, total_non_glycosylation - mutated_non_glycosylation]
    ]
    print(contingency_table)
    oddsratio, pvalue = fisher_exact(contingency_table, alternative=alternative)
    print(source_name, oddsratio, pvalue)
    return oddsratio, pvalue


def are_glycosylation_sites_mutated_more_often_all():
    for disordered in [True, False, None]:
        for source in source_manager.confirmed:
            print(source.name, disordered)
            are_glycosylation_sites_mutated_more_often(source.name, disordered=disordered, alternative='less' if disordered else 'greater')


def are_glycosylation_sites_enriched(source_name: str, population_name: str, disordered=None, alternative='greater'):
    from stats.table import count_mutated_sites

    glycosylation = SiteType.query.filter_by(name='glycosylation').one()
    glyco_filter = SiteType.fuzzy_filter(glycosylation, join=True)

    non_glycosylation = SiteType.query.filter(~SiteType.name.contains('glycosylation')).all()
    non_glyco_filter = Site.types.any(SiteType.id.in_([site_type.id for site_type in non_glycosylation]))

    source = source_manager.source_by_name[source_name]
    population = source_manager.source_by_name[population_name]

    count_glyc = partial(count_mutated_sites, custom_filter=glyco_filter, only_primary=True, disordered=disordered)
    count_not_glyc = partial(count_mutated_sites, custom_filter=non_glyco_filter, only_primary=True, disordered=disordered)

    #         mutated glyc | mutated not glyc
    # cancer |
    # popula |

    contingency_table = [
        [count_glyc(model=source), count_not_glyc(model=source)],
        [count_glyc(model=population), count_not_glyc(model=population)]
    ]
    print(contingency_table)
    oddsratio, pvalue = fisher_exact(contingency_table, alternative=alternative)
    print(source_name, population_name, oddsratio, pvalue)
    return oddsratio, pvalue


def sites_mutated_ratio(
    path='static/plot.png', width=1400, height=900, dpi=72,
    exclude: List[str]=None, glycosylation='together'
):
    from pandas import DataFrame
    from helpers.ggplot2 import GG
    from rpy2.robjects.packages import importr
    from rpy2.robjects import StrVector

    rows = []
    for disorder in [True, False]:
        for source in source_manager.confirmed:
            ratios = sites_mutated_ratio_by_type(
                source.name, disordered=disorder, relative=False, display=False,
                exclude=exclude, glycosylation=glycosylation
            )
            for site_name, percentage in ratios.items():
                row = {
                    'site_type': site_name,
                    'disordered_region': 'Yes' if disorder else 'No',
                    'percentage': percentage,
                    'source': source.name
                }
                rows.append(row)

    df = DataFrame(rows)
    ggplot2 = importr("ggplot2")
    theme_options = {
        'axis.text.x': ggplot2.element_text(angle=90, hjust=1),
        'axis.text': ggplot2.element_text(size=15),
        'text': ggplot2.element_text(size=14),
        'legend.text': ggplot2.element_text(size=14),
        'legend.position': 'bottom'
    }
    plot = (
        GG(ggplot2.ggplot(df, ggplot2.aes_string(x='site_type', y='percentage', fill='disordered_region'))) +
        ggplot2.geom_bar(stat='identity', position=ggplot2.position_stack(reverse=True)) +
        ggplot2.facet_grid('~source') +
        ggplot2.theme(**theme_options) +
        ggplot2.labs(x='Site type', y=r'Percentage of sites affected by mutations', fill='Is site in disordered region?') +
        ggplot2.scale_fill_manual(values=StrVector(["#998ec3", "#f1a340"]))
    )

    if path:
        ggplot2.ggsave(str(path), width=width / dpi, height=height / dpi, dpi=dpi, units='in', bg='transparent')
