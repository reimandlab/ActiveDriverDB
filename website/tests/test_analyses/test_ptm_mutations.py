import pytest

from database_testing import DatabaseTest
from models import MC3Mutation

from .test_run_active_driver import load_cancer_data


class PTMMutationsAnalysisTest(DatabaseTest):

    def test_muts_by_impact(self):

        from stats.plots.ptm_mutations import gather_ptm_muts_impacts

        phosphorylation = load_cancer_data()

        with pytest.warns(Warning, match='This site type has no motifs defined: .*'):
            muts_by_impact_by_gene = gather_ptm_muts_impacts(MC3Mutation, phosphorylation)
        print(muts_by_impact_by_gene)

        assert muts_by_impact_by_gene['direct']['TP53'] == 21
        assert muts_by_impact_by_gene['direct']['ENDOG'] == 0
