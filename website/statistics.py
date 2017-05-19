from database import db
from database import fast_count
import models
from sqlalchemy import and_
from sqlalchemy import or_
from flask import current_app


MAPPINGS_COUNT = 73093771   # this is result of stats.count_mappings() -
# due to long execution time it was precomputed once and hardcoded here


class Statistics:

    def count(self, model):
        return model.query.count()

    def all_confirmed_mutations(self):
        return models.Mutation.query.filter_by(
            is_confirmed=True
        ).count()

    def get_all(self):
        interactions, kinases_covered, groups_covered, proteins_covered = self.count_interactions()
        return {
            'proteins': self.count(models.Protein),
            'genes': self.count(models.Gene),
            'kinases': self.count(models.Kinase),
            'kinase_groups': self.count(models.KinaseGroup),
            'mutations': {
                # both confirmed and MIMP mutations
                'all': self.count(models.Mutation),
                'all_confirmed': self.all_confirmed_mutations(),
                'clinvar': self.count(models.InheritedMutation),
                'esp': self.count(models.ExomeSequencingMutation),
                'cancer': db.session.query(models.Mutation).filter(
                    models.Mutation.meta_cancer.any()
                ).count(),
                # each mutation can have multiple cancer annotations
                'cancer_annotations': self.count(models.CancerMutation),
                'thousand_genomes': self.count(models.The1000GenomesMutation),
                'mimp': self.count(models.MIMPMutation),
                # 'from_many_sources' is very expensive, and it might be better
                # to disable when not necessary (it will be useful for debugging
                # purposes - so we can check if mutations count is correct)
                # 'from_more_than_one_source': self.from_many_sources(),
                'confirmed_in_ptm_sites': self.count_muts_in_sites(),
                'confirmed_with_mimp': self.count_muts_with_mimp(),
            },
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
        return models.Mutation.query.filter_by(
            is_confirmed=True,
            is_ptm_distal=True
        ).count()

    def count_muts_with_mimp(self):
        return models.Mutation.query.filter(
            and_(
                self.get_filter_by_sources(['mimp']),
                models.Mutation.is_confirmed,
            )
        ).count()

    def get_filter_by_sources(self, sources):

        Mutation = models.Mutation

        source_relationship_map = {
            'cancer': Mutation.meta_cancer,
            'clinvar': Mutation.meta_inherited,
            'esp': Mutation.meta_ESP6500,
            '1kg': Mutation.meta_1KG,
            'mimp': Mutation.meta_MIMP,
        }

        filters = and_(
            (
                (
                    source_relationship_map[source].any()
                    if source in ('cancer', 'mimp') else
                    source_relationship_map[source].has()
                )
                for source in sources

            )
        )

        return filters

    def count_by_source(self, sources):
        return models.Mutation.query.filter(
            self.get_filter_by_sources(sources)
        ).count()

    def from_many_sources(self):
        """Counts mutations that have annotations in more
        than one source (eg. in both: TCGA and ClinVar).
        """

        in_all = self.count_by_source(['clinvar', 'esp', '1kg', 'cancer'])

        ev = self.count_by_source(['clinvar', 'esp'])
        kv = self.count_by_source(['clinvar', '1kg'])
        cv = self.count_by_source(['clinvar', 'cancer'])
        ck = self.count_by_source(['cancer', '1kg'])
        ce = self.count_by_source(['cancer', 'esp'])
        ek = self.count_by_source(['1kg', 'esp'])

        cek = self.count_by_source(['1kg', 'esp', 'cancer'])
        ekv = self.count_by_source(['1kg', 'esp', 'clinvar'])
        cev = self.count_by_source(['cancer', 'esp', 'clinvar'])
        ckv = self.count_by_source(['1kg', 'cancer', 'clinvar'])

        return (ev + kv + cv + ck + ce + ek) - (cek + ekv + cev + ckv) + in_all


if current_app.config['LOAD_STATS']:
    stats = Statistics()
    STATISTICS = stats.get_all()
else:
    STATISTICS = ''
