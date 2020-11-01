from database import db
from .model_testing import ModelTest
from models import Mutation
from models import Protein
from models import Site


def create_mutations_with_impact_on_site_at_pos_1():
    return {
        Mutation(position=10): 'none',  # too far away
        Mutation(position=9): 'none',
        Mutation(position=8): 'distal',
        Mutation(position=4): 'distal',
        Mutation(position=3): 'proximal',
        Mutation(position=2): 'proximal',
        Mutation(position=1): 'direct'
    }


class MutationTest(ModelTest):

    def test_default_ref(self):
        p = Protein(sequence='ABC')
        m = Mutation(position=1, protein=p)
        db.session.add(p)
        db.session.commit()
        assert m.ref == 'A'

    def test_impact_on_ptm(self):

        mutations = [Mutation(position=61)]
        protein = Protein(
            refseq='NM_00001',
            mutations=mutations
        )
        db.session.add(protein)
        protein.sites = [Site(position=61), Site(position=54), Site(position=51)]

        mutation = mutations[0]

        assert mutation.impact_on_ptm() == 'direct'

    def test_impact_on_specific_ptm(self):

        # case 0: there are no sites in the protein
        mutations = create_mutations_with_impact_on_site_at_pos_1()

        protein = Protein(
            refseq='NM_00001',
            mutations=mutations.keys()
        )

        db.session.add(protein)

        for mutation in mutations.keys():
            assert mutation.impact_on_ptm() == 'none'

        # case 1: there are some sites in the protein

        protein.sites = [Site(position=1), Site(position=50)]
        site = protein.sites[0]

        for mutation, impact in mutations.items():
            print(mutation)
            assert mutation.impact_on_ptm() == impact
            assert mutation.impact_on_specific_ptm(site) == impact

        # case 2: there are some sites but all will be excluded by a site filter

        def site_filter(sites):
            return []

        for mutation in mutations.keys():
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
