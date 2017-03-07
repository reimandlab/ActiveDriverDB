from database_testing import DatabaseTest
from database import db
import models


class StatisticsTest(DatabaseTest):

    def exposed_stats(self):
        from statistics import Statistics
        s = Statistics()
        return s.get_all()

    def test_simple_models(self):

        model_stats = {
            'pathways': models.Pathway,
            'proteins': models.Protein,
            'genes': models.Gene,
            'kinases': models.Kinase,
            'kinase_groups': models.KinaseGroup,
            'sites': models.Site,
            'cancer': models.Cancer
        }

        for name, model in model_stats.items():
            model_objects = [model() for _ in range(10)]
            db.session.add_all(model_objects)

        stats = self.exposed_stats()

        for name, model in model_stats.items():
            assert stats[name] == 10

    def test_mutations_count(self):

        mutation_models = {
            'mimp': models.MIMPMutation,
            'thousand_genomes': models.The1000GenomesMutation,
            'cancer': models.CancerMutation,
            'esp': models.ExomeSequencingMutation,
            'clinvar': models.InheritedMutation
        }

        for name, model in mutation_models.items():
            m = models.Mutation()
            metadata = model(mutation=m)
            db.session.add(metadata)

        stats = self.exposed_stats()

        for name, model in mutation_models.items():
            assert stats['mutations'][name] == 1

        assert stats['mutations']['all'] == len(mutation_models)

        # confirmed are all without mimp
        assert stats['mutations']['all_confirmed'] == len(mutation_models) - 1

    def test_from_many_sources(self):

        # create one mutation which is present in multiple sources
        m = models.Mutation()
        metadata_1 = models.InheritedMutation(mutation=m)
        metadata_2 = models.CancerMutation(mutation=m)
        db.session.add_all([metadata_1, metadata_2])

        from statistics import Statistics
        statistics = Statistics()

        in_many_sources = statistics.from_many_sources()

        assert in_many_sources == 1
