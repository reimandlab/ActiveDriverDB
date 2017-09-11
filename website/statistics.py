from collections import defaultdict, Counter
from functools import lru_cache
from itertools import combinations

from database import db, get_or_create
from database import fast_count
import models
from sqlalchemy import and_, distinct, func, literal_column, case
from sqlalchemy import or_
from flask import current_app
from models import Mutation, Count, Site, Protein, MC3Mutation, are_details_managed
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


def all_mutated_sites():
    mutated_sites = {}
    site_type_queries = ['']  # empty will match all sites
    site_type_queries.extend(Site.types)
    for site_type in tqdm(site_type_queries):
        mutated_sites[site_type] = count_mutated_sites(site_type)
    print('PTM sites affected by mutations - merged')
    print(mutated_sites)


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

    print('Proteins with PTM muts:')
    print(proteins_with_ptm_muts)
    print('Kinases with PTM muts:')
    print(kinases)
    print('Kinase groups with PTM muts:')
    print(kinase_groups)


def source_specific_nucleotide_mappings():
    from database import bdb
    from genomic_mappings import decode_csv
    from models import Mutation
    from tqdm import tqdm
    from gc import collect

    mutations = defaultdict(str)

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
        for mutation in tqdm(query, total=query.count()):
            mutations[str(mutation[0]) + mutation[1] + str(mutation[2])] += i

    # add merged
    i = str(len(sources_map))
    sources_map[i] = 'merged'
    print('Loading merged mutations:')

    query = (
        db.session.query(Mutation.protein_id, Mutation.alt, Mutation.position)
        .filter(Mutation.is_confirmed == True)
        .yield_per(5000)
    )
    for mutation in tqdm(query, total=query.count()):
        mutations[str(mutation[0]) + mutation[1] + str(mutation[2])] += i

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

    for key, value in counts.items():
        print(sources_map[key], value)


def source_specific_mutated_sites():

    muts_in_ptm_sites = {}
    mimp_muts = {}
    mutated_sites = defaultdict(dict)

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

        site_type_queries = ['']  # empty will match all sites
        site_type_queries.extend(Site.types)

        for site_type in tqdm(site_type_queries):
            mutated_sites[name][site_type] = count_mutated_sites(site_type, model)

    print('Mutations - in PTM sites')
    print(muts_in_ptm_sites)
    print('Mutations - with network-rewiring effect')
    print(mimp_muts)
    print('PTM sites affected by mutations - source specific')
    print(mutated_sites)


def generate_source_specific_summary_table():
    from gc import collect

    counters = [
        source_specific_proteins_with_ptm_mutations,
        all_mutated_sites,
        source_specific_mutated_sites,
        source_specific_nucleotide_mappings
    ]
    for counter in counters:
        counter()
        collect()


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


if current_app.config['LOAD_STATS']:
    stats = Statistics()
    print('Loading statistics')
    STATISTICS = stats.get_all()
else:
    print('Skipping loading statistics')
    STATISTICS = ''
