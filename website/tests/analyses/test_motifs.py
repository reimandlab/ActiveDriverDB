from analyses.motifs import (
    count_muts_and_sites, compile_motifs, mutate_sequence, count_muts_and_sites_from_query,
    select_sites_with_motifs,
)
from database import db
from models import Mutation, Protein, Site, SiteType
from tests.database_testing import DatabaseTest


class MotifAnalysisTest(DatabaseTest):

    def test_mutate(self):

        p = Protein(sequence='ABCDE')
        s = Site(protein=p, position=3, residue='C')

        cases = {
            1: 'XBCDE',
            3: 'ABXDE',
        }

        for position, expected_seq in cases.items():
            m = Mutation(protein=p, position=position, alt='X')

            assert mutate_sequence(s, m, offset=2) == expected_seq

    def test_counting(self):

        motifs_db = compile_motifs({
            # xation happens whenever there is X which is not preceded with or followed by another X
            'xation': {'canonical': '[^X]X[^X]'}
        })

        p = Protein(refseq='NM_007', id=1, sequence='_X_________X________XXX')

        mutations = [
            Mutation(protein=p, position=1, alt='X'),   # proximal, breaking
            Mutation(protein=p, position=1, alt='o'),   # proximal, non-breaking
            Mutation(protein=p, position=2, alt='Y'),   # direct, breaking
        ]

        canonical_sites = [
            Site(protein=p, position=2, type={'xation'}),     # canonical, seriously mutated and broken
            Site(protein=p, position=12, type={'xation'}),    # canonical, not mutated
        ]
        other_sites = [
            Site(protein=p, position=22, type={'xation'}),    # non-canonical motif, not mutated
        ]
        all_sites = canonical_sites + other_sites

        db.session.add(p)
        db.session.commit()

        counts = count_muts_and_sites_from_query(Mutation.query, SiteType(name='xation'), motifs_db)
        assert counts.muts_around_sites_with_motif == 3
        assert counts.muts_breaking_sites_motif == 2
        assert counts.sites_with_broken_motif['canonical'] == {canonical_sites[0]}
        assert counts.sites_with_motif['canonical'] == set(canonical_sites)

        counts_two = count_muts_and_sites(mutations, all_sites, SiteType(name='xation'), motifs_db)

        assert counts == counts_two

        x_motifs = motifs_db['xation']

        selection = select_sites_with_motifs(Site.query, x_motifs)

        assert selection['canonical'] == set(canonical_sites)
        assert select_sites_with_motifs(all_sites, x_motifs) == selection
