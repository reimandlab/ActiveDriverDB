from itertools import combinations
from typing import List

from sqlalchemy import and_, func, distinct, or_

import models
from database import db, fast_count
from models import Mutation, are_details_managed, MC3Mutation, source_manager, MutationSource

from .store import counter
from .store import CountStore


def models_counter(model, name=None):
    def count(self):
        return self.count(model)
    return counter(count, name)


def mutations_counter(func):
    return counter(func, name='mutations_' + func.__name__)


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
    def count_by_sources(sources: List[MutationSource]):
        return Mutation.query.filter(Mutation.in_sources(*sources)).count()

    def __init__(self):

        for source_model in source_manager.all:
            # dirty trick: 1KGenomes is not a valid name in Python
            name = 'mutations_' + source_model.name.replace('1', 'T')

            def muts_counter(_self):
                return self.count_by_sources([source_model])

            self.register(counter(muts_counter, name=name))

        for source_model in filter(lambda model: are_details_managed(model), source_manager.all):
            name = f'mutations_{source_model.name}_annotations'

            self.register(
                models_counter(source_model, name=name)
            )

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
                Mutation.in_sources(models.MIMPMutation),
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
            source
            for source in source_manager.all
            if source.is_confirmed and source.is_visible
        ]
        count = 0

        for i in range(2, len(sources) + 1):
            sign = 1 if i % 2 == 0 else -1
            for combination in combinations(sources, i):
                count += sign * self.count_by_sources(combination)

        return count

    @staticmethod
    def count(model):
        return db.session.query(model).count()

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
