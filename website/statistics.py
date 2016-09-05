import models


class Statistics:

    def count(self, model):
        return model.query.count()

    def get_all(self):
        return {
            'proteins': self.count(models.Protein),
            'genes': self.count(models.Gene),
            'kinases': self.count(models.Kinase),
            'kinase_groups': self.count(models.KinaseGroup),
            'mutations': {
                'all': self.count(models.Mutation),
                'clinvar': self.count(models.InheritedMutation),
                'esp': self.count(models.ExomeSequencingMutation),
                'cancer': self.count(models.CancerMutation),
                'thousand_genomes': self.count(models.The1000GenomesMutation),
                'mimp': self.count(models.MIMPMutation),
            },
            'sites': self.count(models.Site),
            'cancer': self.count(models.Cancer),
        }

stats = Statistics()

STATISTICS = stats.get_all()
