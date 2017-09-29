import random
from collections import defaultdict, Counter, namedtuple
from functools import lru_cache
from itertools import combinations
from statistics import median

from database import db, get_or_create, join_unique
from database import fast_count
import models
from sqlalchemy import and_, distinct, func, literal_column, case
from sqlalchemy import or_
from flask import current_app
from models import Count, Site, Protein, Gene, are_details_managed, The1000GenomesMutation
from models import Mutation, InheritedMutation, MC3Mutation
from tqdm import tqdm

counters = {}


def counter(func, name=None):
    if not name:
        name = func.__name__
    counters[name] = func
    return lru_cache(maxsize=1)(func)


def models_counter(model):
    def counter(self):
        return self.count(model)
    counter.to_be_registered = True
    return counter


def mutations_counter(func):
    return counter(func, name='mutations_' + func.__name__)


def get_methods(instance):

    def is_method(member):
        name, value = member
        return not name.startswith('_') and callable(value)

    all_members = {name: getattr(instance, name) for name in dir(instance)}

    return filter(is_method, all_members.items())


class CountStore:

    @property
    def counters(self):
        return counters

    def calc_all(self):
        for name, counter in self.counters.items():
            model, new = get_or_create(Count, name=name)
            if hasattr(counter, '__self__'):
                value = counter()
            else:
                value = counter(self)
            model.value = value
            print(name, value)
            if new:
                db.session.add(model)

    def get_all(self):

        counts = {
            counter_name: db.session.query(Count.value).filter(Count.name == counter_name).scalar() or 0
            for counter_name in self.counters.keys()
        }

        return counts


class Statistics(CountStore):
    """This module calculates, stores and retrieves counts of data in database.

    On initialization any instance of Statistics class can be used to calculate
    counts of various data entities which are hard-coded in the class methods.

        stats = Statistics()                # initialize a new instance

    If accessed directly after initialization, each counter's method will
    be executed at run time, which may cause delayed response:

        proteins_cnt = stats.proteins()     # this may take a few seconds now
        print(proteins_cnt)

    You can compute all counts at once, so those can be saved to database afterwards:

        stats.calc_all()                    # this will take several minutes
        db.session.commit()                 # save results in database

    After using 'calc_all()', the results can be obtained from database:

        counts = stats.get_all()

    You can access the pre-defined counts instantly, with no delay now.

        print(counts['muts']['ClinVar'])
        print(counts['proteins'])
    """

    def get_all(self):
        """Retrieves data counts from database in form of dict,
        where keys are model names and values are entity counts.

        Mutations counts are accessible in sub-dict called 'muts'.
        """
        all_counts = super().get_all()

        counts = {}
        mutation_counts = {}

        for counter_name, value in all_counts.items():
            if counter_name.startswith('mutations_'):
                counter_name = counter_name[10:]    # strip off "mutations_"
                mutation_counts[counter_name] = value
            else:
                counts[counter_name] = value

        counts['muts'] = mutation_counts

        return counts

    @staticmethod
    def get_filter_by_sources(sources):

        filters = and_(
            (
                (
                    Mutation.get_relationship(source).any()
                    if are_details_managed(source) else
                    Mutation.get_relationship(source).has()
                )
                for source in sources

            )
        )

        return filters

    def count_by_source(self, sources):
        return Mutation.query.filter(
            self.get_filter_by_sources(sources)
        ).count()

    def __init__(self):

        for model in Mutation.source_specific_data:
            # dirty trick: 1KGenomes is not a valid name in Python
            name = 'mutations_' + model.name.replace('1', 'T')

            def muts_counter(self, model=model):
                return self.count_mutations(model)
            muts_counter.to_be_registered = True

            self.__dict__[name] = muts_counter

        for model in filter(lambda model: are_details_managed(model), Mutation.source_specific_data):
            name = 'mutations_' + model.name + '_annotations'

            self.__dict__[name] = models_counter(model)

        for name, method in get_methods(self):
            if hasattr(method, 'to_be_registered'):
                self.__dict__[name] = counter(method, name)

    @mutations_counter
    def all(self):
        """Either confirmed or not."""
        return self.count(Mutation)

    @mutations_counter
    def all_confirmed(self):
        return Mutation.query.filter_by(
            is_confirmed=True
        ).count()

    @mutations_counter
    def confirmed_in_ptm_sites(self):
        return Mutation.query.filter_by(
            is_confirmed=True,
            is_ptm_distal=True
        ).count()

    @mutations_counter
    def confirmed_with_mimp(self):
        return Mutation.query.filter(
            and_(
                self.get_filter_by_sources([models.MIMPMutation]),
                Mutation.is_confirmed,
            )
        ).count()

    # 'from_more_than_one_source' is very expensive, and it might be better
    # to disable when not necessary (it will be useful for debugging
    # purposes - so we can check if mutations count is correct)
    # @mutations_counter
    def from_more_than_one_source(self):
        """Counts mutations that have annotations in more
        than one source (eg. in both: TCGA and ClinVar).
        """

        sources = [
            model
            for model in Mutation.source_specific_data
            if model != models.MIMPMutation and model != models.UserUploadedMutation
        ]
        count = 0

        for i in range(2, len(sources) + 1):
            sign = 1 if i % 2 == 0 else -1
            for combination in combinations(sources, i):
                count += sign * self.count_by_source(combination)

        return count

    @staticmethod
    def count(model):
        return db.session.query(model).count()

    def count_mutations(self, mutation_class):
        return db.session.query(Mutation).filter(
            self.get_filter_by_sources([mutation_class])
        ).count()

    def mc3_exomes(self):
        return len(
            {
                sample.split('-')[2]
                for m in MC3Mutation.query
                for sample in m.samples.split(',')
            }
        )

    @counter
    def proteins(self):
        return self.count(models.Protein)

    genes = models_counter(models.Gene)
    kinases = models_counter(models.Kinase)
    kinase_groups = models_counter(models.KinaseGroup)
    sites = models_counter(models.Site)
    pathways = models_counter(models.Pathway)
    cancer = models_counter(models.Cancer)

    @counter
    def mappings(self):
        from database import bdb
        return len(bdb)

    @counter
    def annotations(self):
        # "number of mutation annotations
        # (all DNA>protein table + MIMP annotations)"
        return self.count(models.MIMPMutation) + self.mappings()

    @counter
    def kinases_covered(self):
        return fast_count(db.session.query(models.Kinase).filter(models.Kinase.sites.any()))

    @counter
    def kinase_groups_covered(self):
        return fast_count(db.session.query(models.KinaseGroup).filter(models.KinaseGroup.sites.any()))

    @counter
    def interactions(self):
        return (
            fast_count(db.session.query(models.Site).join(models.Kinase, models.Site.kinases)) +
            fast_count(db.session.query(models.Site).join(models.KinaseGroup, models.Site.kinase_groups))
        )

    @counter
    def proteins_covered(self):
        return (
            db.session.query(
                func.count(
                    distinct(models.Site.protein_id)
                )
            )
            .filter(
                or_(
                    models.Site.kinases.any(),
                    models.Site.kinase_groups.any()
                )
            )
            .scalar()
        )


def count_mutated_sites(site_type, model=None):
    filters = [
        Mutation.protein_id == Protein.id,
        Site.protein_id == Protein.id,
        Mutation.precomputed_is_ptm
    ]
    if site_type:
        filters.append(Site.type.like('%' + site_type + '%'))
    query = (
        db.session.query(
            func.count(distinct(case(
                [
                    (
                        (
                            Mutation.position.between(
                                Site.position - 7,
                                Site.position + 7
                            )
                        ),
                        Site.id
                    )
                ],
                else_=literal_column('NULL')
            )))
        )
        .filter(and_(*filters))
        .join(Mutation, Site.protein_id == Mutation.protein_id)
    )
    if model:
        query = query.filter(Statistics.get_filter_by_sources([model]))
    else:
        query = query.filter(Mutation.is_confirmed == True)
    return query.scalar()


def mutation_sources():
    sources = {}

    for name, source in Mutation.sources_dict.items():
        if name == 'user':
            continue
        sources[name] = Mutation.get_source_model(name)

    return sources


def source_specific_proteins_with_ptm_mutations():

    source_models = mutation_sources()
    source_models['merged'] = None

    proteins_with_ptm_muts = {}
    kinases = {}
    kinase_groups = {}
    for name, model in tqdm(source_models.items()):
        query = (
            db.session.query(distinct(Protein.id))
            .filter(Protein.has_ptm_mutations_in_dataset(model) == True)
        )
        proteins_with_ptm_muts[name] = query.count()
        kinases[name] = (
            db.session.query(distinct(models.Kinase.id))
            .join(Protein)
            .filter(Protein.has_ptm_mutations_in_dataset(model) == True)
        ).count()
        kinase_groups[name] = (
            db.session.query(distinct(models.KinaseGroup.id))
            .join(models.Kinase)
            .join(Protein)
            .filter(Protein.has_ptm_mutations_in_dataset(model) == True)
        ).count()

    return {
        'Proteins with PTM muts': proteins_with_ptm_muts,
        'Kinases with PTM muts': kinases,
        'Kinase groups with PTM muts': kinase_groups
    }


def source_specific_nucleotide_mappings():
    from database import bdb
    from genomic_mappings import decode_csv
    from models import Mutation
    from tqdm import tqdm
    from gc import collect

    mutations = defaultdict(str)

    def count_mutations(mutations_query):
        for mutation in tqdm(mutations_query, total=mutations_query.count()):
            mutations[str(mutation[0]) + mutation[1] + str(mutation[2])] += i

    sources_map = {str(i): model for i, model in enumerate(mutation_sources().values())}

    print('Loading mutations from sources:')
    for i, model in tqdm(sources_map.items(), total=len(sources_map)):
        query = (
            db.session.query(Mutation.protein_id, Mutation.alt, Mutation.position)
            .filter(Statistics.get_filter_by_sources([model]))
            # no need for '.filter(Mutation.is_confirmed==True)'
            # (if it is in source of interest, it is confirmed - we do not count MIMPs here)
            .yield_per(5000)
        )
        count_mutations(query)

    # add merged
    i = str(len(sources_map))
    sources_map[i] = 'merged'
    print('Loading merged mutations:')

    query = (
        db.session.query(Mutation.protein_id, Mutation.alt, Mutation.position)
        .filter(Mutation.is_confirmed == True)
        .yield_per(5000)
    )
    count_mutations(query)

    print('Mutations loaded')
    collect()

    def iterate_known_muts_sources():
        for value in tqdm(bdb.values(), total=len(bdb.db)):
            for item in map(decode_csv, value):
                sources = mutations.get(str(item['protein_id']) + item['alt'] + str(item['pos']))
                if sources:
                    yield sources

    counts = defaultdict(int)
    fields_ids = [source_id for source_id in sources_map.keys()]

    for sources in iterate_known_muts_sources():
        for field in fields_ids:
            if field in sources:
                counts[field] += 1

    return {
        'Nucleotide mappings': {
            sources_map[key]: value
            for key, value in counts.items()
        }
    }


def source_specific_mutated_sites():

    muts_in_ptm_sites = {}
    mimp_muts = {}
    mutated_sites = defaultdict(dict)

    site_type_queries = ['']  # empty will match all sites
    site_type_queries.extend(Site.types)

    for name, model in mutation_sources().items():
        count = (
            Mutation.query
            .filter_by(is_confirmed=True, is_ptm_distal=True)
            .filter(Statistics.get_filter_by_sources([model]))
            .count()
        )
        muts_in_ptm_sites[name] = count

        mimp_muts[name] = (
            Mutation.query
            .filter(
                and_(
                    Statistics.get_filter_by_sources([models.MIMPMutation, model]),
                    Mutation.is_confirmed,
                )
            ).count()
        )

        for site_type in tqdm(site_type_queries):
            mutated_sites[name][site_type] = count_mutated_sites(site_type, model)

    all_mutated_sites = {}

    for site_type in tqdm(site_type_queries):
        all_mutated_sites[site_type] = count_mutated_sites(site_type)

    mutated_sites['merged'] = all_mutated_sites

    return {
        'Mutations - in PTM sites': muts_in_ptm_sites,
        'Mutations - with network-rewiring effect': mimp_muts,
        'PTM sites affected by mutations': mutated_sites
    }


def generate_source_specific_summary_table():
    from gc import collect

    table_chunks = [
        source_specific_proteins_with_ptm_mutations,
        source_specific_mutated_sites,
        source_specific_nucleotide_mappings,
        sites_counts
    ]
    table = {}
    for table_chunk_generator in table_chunks:
        chunk = table_chunk_generator()
        table.update(chunk)
        collect()

    print(table)

    return table


def sites_counts():
    counts = {}
    site_types = ['']  # empty will match all sites
    site_types.extend(Site.types)
    for site_type in site_types:
        count = Site.query.filter(Site.type.like('%' + site_type + '%')).count()
        counts[site_type] = count
    return {'PTM sites': counts}


def hypermutated_samples(path, threshold=900):
    from helpers.parsers import iterate_tsv_gz_file
    from collections import Counter

    samples_cnt = Counter()
    muts = defaultdict(set)
    total = 0

    for line in iterate_tsv_gz_file(path):
        total += 1
        muts[','.join([line[0], '%x' % int(line[1]), '%x' % int(line[2]), line[3], line[4]])].add(line[10])

    for samples in muts.values():
        for sample in samples:
            samples_cnt[sample] += 1

    hypermutated = {}
    for sample, count in samples_cnt.most_common():
        if count > threshold:
            hypermutated[sample] = count
        else:
            break

    print('There are %s hypermutated samples.' % len(hypermutated))
    print(
        'Hypermutated samples represent %s percent of analysed mutations.'
        %
        (sum(hypermutated.values()) / total * 100)
    )
    return hypermutated


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


def test_enrichment_of_ptm_mutations_among_mutations_subset(subset_query, reference_query, iterations_count=100000):
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
            ptms: list of counts of PTM sites discovered in each of sampling iterations
    """
    ptm_enriched_absolute = 0
    ptm_enriched_percentage = 0

    is_ptm = Mutation.precomputed_is_ptm

    # 1.
    all_mutations = subset_query.count()                        # C
    ptm_mutations = subset_query.filter(is_ptm).count()         # D
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

    result_tuple = namedtuple('EnrichmentAnalysisResult', 'ptms median median_percentage, p_value, p_value_percentage')

    return result_tuple(
        enriched_ptms,
        median_ptms,
        median_percentage,
        ptm_enriched_absolute / iterations_count,
        ptm_enriched_percentage / iterations_count
    )


def get_confirmed_mutations(sources, only_preferred=True, genes=None):

    def only_from_primary_isoforms(mutations_query):

        mutations_query = join_unique(mutations_query, Protein)
        return mutations_query.filter(Protein.is_preferred_isoform)

    mutations = Mutation.query.filter_by(is_confirmed=True)
    mutations = only_from_primary_isoforms(mutations)

    if genes:
        mutations = mutations.filter(Protein.id.in_([g.preferred_isoform_id for g in genes]))

    selected_mutations = mutations.filter(Statistics.get_filter_by_sources(sources))
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


def parametric_test_ptm_enrichment(tested_source, reference_source, tested_genes, ref_genes):
    """Uses only mutations from primary isoforms."""

    # e.g. 1000Genomes
    reference_mutations = get_confirmed_mutations([reference_source], genes=ref_genes)

    # e.g. ClinVar
    tested_mutations = get_confirmed_mutations([tested_source], genes=tested_genes)

    result = test_enrichment_of_ptm_mutations_among_mutations_subset(tested_mutations, reference_mutations)
    print(result)

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


def load_cancer_census(cancer_census_path='data/disease_muts_in_ptm_sites/census.tsv'):
    """Load genes from cancer census.

    Args:
        cancer_census_path: this file needs to be downloaded from COSMIC
    """

    gene_names = set()
    with open(cancer_census_path) as f:
        for line in f:
            gene_names.add(line.split('\t')[0])

    gene_names.remove('Gene Symbol')

    cancer_genes = set()

    for name in gene_names:
        g = Gene.query.filter_by(name=name).first()
        if g:
            cancer_genes.add(g)
        else:
            print('%s' % name)
    return cancer_genes


def get_genes_with_mutations_from_sources(sources, only_genes_with_ptm_sites=False):
    query = (
        db.session.query(Gene)
        .join(Protein, Gene.preferred_isoform_id == Protein.id)
        .join(Mutation)
    )
    query = query.filter(Statistics.get_filter_by_sources(sources))

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
            Statistics.get_filter_by_sources(sources)
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


if current_app.config['LOAD_STATS']:
    stats = Statistics()
    print('Loading statistics')
    STATISTICS = stats.get_all()
else:
    print('Skipping loading statistics')
    STATISTICS = ''
