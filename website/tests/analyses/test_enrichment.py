from analyses.enrichment import most_mutated_sites
from database import db
from models import Mutation, Site, Protein, InheritedMutation, MC3Mutation, ClinicalData, Gene
from database_testing import DatabaseTest


class MutationTest(DatabaseTest):

    def test_mutated_sites(self):

        g = Gene(name='Gene X')
        p = Protein(refseq='NM_007', sequence='ABCDEFGHIJKLMNOPQRSTUVWXYZ', gene=g)
        g.preferred_isoform = p

        sites = {
            # ClinVar muts and TCGA muts but different, with total count = 5 (3 + 2)
            'A': Site(position=1, residue='A', protein=p),
            # ClinVar muts intersection TCGA muts, total count = 4 (2 + 2)
            'K': Site(position=11, residue='K', protein=p),
            # Only TCGA muts, total count = 3 (1 + 2)
            'U': Site(position=21, residue='U', protein=p, type={'glycosylation'})
        }

        def mut(pos):
            return Mutation(position=pos, alt='X', protein=p)

        intersecting_mut = mut(11)

        mutations = [
            # the first site (1 A)
            InheritedMutation(
                mutation=mut(1),
                clin_data=[ClinicalData(), ClinicalData(), ClinicalData()]
            ),
            MC3Mutation(mutation=mut(2), count=2),
            # the second site (11 K)
            InheritedMutation(
                mutation=intersecting_mut,
                clin_data=[ClinicalData(), ClinicalData()]
            ),
            MC3Mutation(mutation=intersecting_mut, count=2),
            # the third site (21 U)
            MC3Mutation(mutation=mut(20), count=1),
            MC3Mutation(mutation=mut(22), count=2),
        ]

        db.session.add_all(mutations)
        db.session.add_all([p, g])
        db.session.add_all(sites.values())
        db.session.commit()

        sites_with_clinvar = most_mutated_sites([InheritedMutation]).all()
        assert sites_with_clinvar == [(sites['A'], 3), (sites['K'], 2)]

        sites_with_mc3 = most_mutated_sites([MC3Mutation]).all()
        assert set(sites_with_mc3) == {(sites['A'], 2), (sites['K'], 2), (sites['U'], 3)}

        both_sources = [MC3Mutation, InheritedMutation]

        sites_with_muts_in_both_intersection = most_mutated_sites(both_sources, intersection=True).all()
        assert sites_with_muts_in_both_intersection == [(sites['K'], 4)]

        sites_with_muts_in_both = most_mutated_sites(both_sources, intersection=False).all()
        assert sites_with_muts_in_both == [(sites['A'], 5), (sites['K'], 4)]

        glyco_sites_with_mc3 = most_mutated_sites([MC3Mutation], site_type='glycosylation').all()
        assert glyco_sites_with_mc3 == [(sites['U'], 3)]
