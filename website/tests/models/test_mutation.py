from database import db
from model_testing import ModelTest
from models import Mutation
from models import Protein
from models import Site


class MutationTest(ModelTest):

    def test_impact_on_specific_ptm(self):

        # case 0: there are no sites in the protein

        mutations = {
            'none': Mutation(position=10),    # too far
            'distal': Mutation(position=8),
            'proximal': Mutation(position=4),
            'direct': Mutation(position=1)
        }

        protein = Protein(
            refseq='NM_00001',
            mutations=mutations.values()
        )

        db.session.add(protein)

        for mutation in mutations.values():
            assert mutation.impact_on_ptm() == 'none'

        # case 1: there are some sites in the protein

        protein.sites = [Site(position=1), Site(position=50)]

        for impact, mutation in mutations.items():
            assert mutation.impact_on_ptm() == impact

        # case 2: there are some sites but all will be excluded by a site filter

        def site_filter(sites):
            return []

        for mutation in mutations.values():
            assert mutation.impact_on_ptm(site_filter=site_filter) == 'none'

    def test_find_closest_sites(self):

        mutations = {
            0: Mutation(position=0),
            1: Mutation(position=5),
            2: Mutation(position=12)
        }

        protein = Protein(
            refseq='NM_00001',
            mutations=mutations.values(),
            sites=[Site(position=10), Site(position=14),  Site(position=15)]
        )

        db.session.add(protein)

        for sites_found_cnt, mutation in mutations.items():
            sites_found = mutation.find_closest_sites()
            assert len(sites_found) == sites_found_cnt
