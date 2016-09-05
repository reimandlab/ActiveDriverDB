from database import db
import models


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
            },
            'sites': self.count(models.Site),
            'cancer': self.count(models.Cancer),
        }

stats = Statistics()

STATISTICS = stats.get_all()
