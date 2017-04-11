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

    def test_sites(self):

        mutations = [
            Mutation(position=x)
            for x in (0, 5, 12, 57)
        ]

        protein = Protein(
            refseq='NM_00002',
            mutations=mutations,
            sites=[
                Site(position=x)
                for x in (10, 14, 15, 57)
            ]
        )

        db.session.add(protein)
        db.session.commit()

        # ==test_find_closest_sites==

        # for mutation at position 0 there is no closest site;
        # for mutation at position 5 there should be 1 closest site
        expected_closest_sites = dict(zip(mutations, [0, 1, 2, 1]))

        for mutation, expected_sites_cnt in expected_closest_sites.items():
            sites_found = mutation.find_closest_sites()
            assert len(sites_found) == expected_sites_cnt

        # ==test_get_affected_ptm_sites==

        expected_affected_sites = dict(zip(mutations, [0, 1, 3, 1]))

        for mutation, expected_sites_cnt in expected_affected_sites.items():
            sites_found = mutation.get_affected_ptm_sites()
            assert len(sites_found) == expected_sites_cnt
