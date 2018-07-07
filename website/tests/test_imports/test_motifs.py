from database import db
from imports.protein_data import sites_motifs
from database_testing import DatabaseTest
from models.bio.sites import SiteMotif
from models.bio import SiteType


class TestImport(DatabaseTest):

    def test_motifs(self):
        n_glycosylation = SiteType(name='N-glycosylation')
        db.session.add(n_glycosylation)
        db.session.commit()

        motifs = sites_motifs([
            [
                'N-glycosylation', 'N-linked Typical Motif', '.{7}N[^P][ST].{5}',
                [' ' * 7 + 'N S' + ' ' * 5, ' ' * 7 + 'N T' + ' ' * 5]
            ]
        ])

        assert len(motifs) == 1
        n_motif: SiteMotif = motifs[0]

        assert n_motif.name == 'N-linked Typical Motif'
        assert n_motif.site_type == n_glycosylation
        assert n_motif.pattern == '.{7}N[^P][ST].{5}'
