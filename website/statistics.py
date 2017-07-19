from functools import lru_cache
from itertools import combinations

from database import db, get_or_create
from database import fast_count
import models
from sqlalchemy import and_, distinct, func
from sqlalchemy import or_
from flask import current_app
from models import Mutation, Count

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


if current_app.config['LOAD_STATS']:
    stats = Statistics()
    print('Loading statistics')
    STATISTICS = stats.get_all()
else:
    print('Skipping loading statistics')
    STATISTICS = ''
