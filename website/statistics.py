from collections import defaultdict
from functools import lru_cache
from itertools import combinations

from database import db, get_or_create
from database import fast_count
import models
from sqlalchemy import and_, distinct, func, literal_column, case, text
from sqlalchemy import or_
from flask import current_app
from models import Mutation, Count, Site, Protein
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


class Statistics:

    @property
    def counters(self):
        return counters

    @staticmethod
    def get_filter_by_sources(sources):

        filters = and_(
            (
                (
                    Mutation.get_relationship(source).any()
                    if source.details_manager else
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

    def get_methods(self):

        def is_method(member):
            name, value = member
            return not name.startswith('_') and callable(value)

        all_members = {name: getattr(self, name) for name in dir(self)}

        return filter(is_method, all_members.items())

    def __init__(self):

        for model in Mutation.source_specific_data:
            # dirty trick: 1KGenomes is not valid name in python
            name = 'mutations_' + model.name.replace('1', 'T')

            def muts_counter(self, model=model):
                return self.count_mutations(model)
            muts_counter.to_be_registered = True

            self.__dict__[name] = muts_counter

        for model in filter(lambda model: model.details_manager, Mutation.source_specific_data):
            name = 'mutations_' + model.name + '_annotations'

            self.__dict__[name] = models_counter(model)

        for name, method in self.get_methods():
            if hasattr(method, 'to_be_registered'):
                self.__dict__[name] = counter(method, name)

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

        mutation_counts = {
            counter_name[10:]: db.session.query(Count.value).filter(Count.name == counter_name).scalar() or 0
            for counter_name in self.counters.keys()
            if counter_name.startswith('mutations_')
        }

        counts = {
            counter_name: db.session.query(Count.value).filter(Count.name == counter_name).scalar() or 0
            for counter_name in self.counters.keys()
            if not counter_name.startswith('mutations_')
        }

        counts['muts'] = mutation_counts

        return counts

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
            if model != models.MIMPMutation
        ]
        count = 0

        for i in range(2, len(sources) - 1):
            sign = 1 if i % 2 == 0 else -1
            for combination in combinations(sources, i):
                count += sign * self.count_by_source(combination)

        return count

    @staticmethod
    def count(model):
        return db.session.query(model).count()

    def count_mutations(self, mutation_class):
        if mutation_class.details_manager is not None:
            return db.session.query(Mutation).filter(
                self.get_filter_by_sources([mutation_class])
            ).count()
        else:
            return self.count(mutation_class)

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
    return query.scalar()


def all_mutated_sites():
    mutated_sites = {}
    site_type_queries = ['']  # empty will match all sites
    site_type_queries.extend(Site.types)
    for site_type in tqdm(site_type_queries):
        mutated_sites[site_type] = count_mutated_sites(site_type)
    print(mutated_sites)


def source_specific_proteins_with_ptm_mutations():

    source_models = {'merged': None}

    for name, source in Mutation.sources_dict.items():
        if name == 'user':
            continue
        source_models[name] = Mutation.get_source_model(name)

    proteins_with_ptm_muts = {}
    kinases = {}
    kinase_groups = {}
    for name, model in source_models.items():
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

    print(proteins_with_ptm_muts)
    print(kinases)
    print(kinase_groups)


def generate_source_specific_summary_table():

    muts_in_ptm_sites = {}
    mimp_muts = {}
    mutated_sites = defaultdict(dict)

    sources = Mutation.sources_dict
    for name, source in sources.items():
        if name == 'user':
            continue
        model = Mutation.get_source_model(name)
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

    print(mutated_sites)


if current_app.config['LOAD_STATS']:
    stats = Statistics()
    print('Loading statistics')
    STATISTICS = stats.get_all()
else:
    print('Skipping loading statistics')
    STATISTICS = ''
