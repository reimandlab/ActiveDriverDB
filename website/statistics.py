from database import db
import models
from sqlalchemy import and_


class Statistics:

    def count(self, model):
        return model.query.count()

    def all_confirmed_mutations(self):
        return models.Mutation.query.filter_by(is_confirmed=True).count()

    def get_all(self):
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
                # to disable when not necessary (it will be useful for debuging
                # purposes - so we can check if mutations count is correct)
                # 'from_more_than_one_source': self.from_many_sources(),
            },
            'sites': self.count(models.Site),
            'cancer': self.count(models.Cancer),
        }

    def get_filter_by_sources(self, sources):

        Mutation = models.Mutation

        source_relationship_map = {
            'clinvar': Mutation.meta_inherited,
            'esp': Mutation.meta_ESP6500,
            '1kg': Mutation.meta_1KG,
            'mimp': Mutation.meta_MIMP,
        }

        filters = and_(
            (
                source_relationship_map[source].has()
                for source in sources
                if source != 'cancer'
            )
        )

        if 'cancer' in sources:
            filters = and_(filters, Mutation.meta_cancer.any())

        return filters

    def count_by_source(self, sources):
        return models.Mutation.query.filter(
            self.get_filter_by_sources(sources)
        ).count()

    def from_many_sources(self):

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


stats = Statistics()

STATISTICS = stats.get_all()
