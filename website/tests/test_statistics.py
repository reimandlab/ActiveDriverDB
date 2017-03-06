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
