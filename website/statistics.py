from itertools import combinations

from database import db
from database import fast_count
import models
from sqlalchemy import and_
from sqlalchemy import or_
from flask import current_app
from models import Mutation


MAPPINGS_COUNT = 73093771   # this is result of stats.count_mappings() -
# due to long execution time it was precomputed once and hardcoded here


class Statistics:

    @staticmethod
    def count(model):
        return db.session.query(model).count()

    @staticmethod
    def all_confirmed_mutations():
        return Mutation.query.filter_by(
            is_confirmed=True
        ).count()

    def count_mutations(self, mutation_class):
        if mutation_class.details_manager is not None:
            return db.session.query(Mutation).filter(
                self.get_filter_by_sources([mutation_class])
            ).count()
        else:
            return self.count(mutation_class)

    def get_all(self):
        interactions, kinases_covered, groups_covered, proteins_covered = self.count_interactions()

        mutation_counts = {
            # dirty trick: 1KGenomes is not valid name in python
            model.name.replace('1', 'T'): self.count_mutations(model)
            for model in Mutation.source_specific_data
        }

        annotation_counts = {
            model.name + '_annotations': self.count(model)
            for model in filter(
                lambda model: model.details_manager,
                Mutation.source_specific_data
            )
        }

        mutation_stats = {
                # both confirmed and MIMP mutations
                'all': self.count(Mutation),
                'all_confirmed': self.all_confirmed_mutations(),
                # 'from_many_sources' is very expensive, and it might be better
                # to disable when not necessary (it will be useful for debugging
                # purposes - so we can check if mutations count is correct)
                # 'from_more_than_one_source': self.from_many_sources(),
                'confirmed_in_ptm_sites': self.count_muts_in_sites(),
                'confirmed_with_mimp': self.count_muts_with_mimp()
        }
        mutation_stats.update(mutation_counts)
        mutation_stats.update(annotation_counts)

        return {
            'proteins': self.count(models.Protein),
            'genes': self.count(models.Gene),
            'kinases': self.count(models.Kinase),
            'kinase_groups': self.count(models.KinaseGroup),
            'muts': mutation_stats,
            'sites': self.count(models.Site),
            'pathways': self.count(models.Pathway),
            'cancer': self.count(models.Cancer),
            # "number of mutation annotations
            # (all DNA>protein table + MIMP annotations)"
            'annotations': (
                self.count(models.MIMPMutation) +
                MAPPINGS_COUNT   # self.count_mappings()
            ),
            'interactions': interactions,
            'kinases_covered': kinases_covered
        }

    @staticmethod
    def count_interactions():

        kinases_covered = fast_count(db.session.query(models.Kinase).filter(models.Kinase.sites.any()))
        kinase_groups_covered = fast_count(db.session.query(models.KinaseGroup).filter(models.KinaseGroup.sites.any()))
        proteins_covered = len(
            db.session.query(models.Site.protein_id)
                .filter(or_(
                    models.Site.kinases.any(),
                    models.Site.kinase_groups.any()
                ))
                .distinct().
                all()
            )
        all_interactions = (
            fast_count(db.session.query(models.Site).join(models.Kinase, models.Site.kinases)) +
            fast_count(db.session.query(models.Site).join(models.KinaseGroup, models.Site.kinase_groups))
        )

        return all_interactions, kinases_covered, kinase_groups_covered, proteins_covered

    @staticmethod
    def count_mappings():
        from database import bdb
        return len(bdb)

    @staticmethod
    def count_muts_in_sites():
        return Mutation.query.filter_by(
            is_confirmed=True,
            is_ptm_distal=True
        ).count()

    def count_muts_with_mimp(self):
        return Mutation.query.filter(
            and_(
                self.get_filter_by_sources([models.MIMPMutation]),
                Mutation.is_confirmed,
            )
        ).count()

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

    def from_many_sources(self):
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


if current_app.config['LOAD_STATS']:
    stats = Statistics()
    STATISTICS = stats.get_all()
else:
    STATISTICS = ''
