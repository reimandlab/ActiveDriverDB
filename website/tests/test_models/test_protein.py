from database import db
from .model_testing import ModelTest
from models import Protein, Site, Gene


class ProteinTest(ModelTest):

    def test_has_sites_in_range(self):
        mutation_position = 100

        sites_result = {
            (93, 107): True,
            (92, 108): False,
            (100,): True,
            tuple(): False,
            (90,): False,
            (110,): False,
            (94, 95, 96, 97, 98, 99): True,
            (101, 102, 103, 104, 105, 106): True,
            (93,): True,
            (107,): True
        }

        for sites_positions, expected_result in sites_result.items():
            protein = Protein(
                sites=[
                    Site(position=pos)
                    for pos in sites_positions
                ]
            )
            db.session.add(protein)
            result = protein.has_sites_in_range(mutation_position - 7, mutation_position + 7)
            assert result == expected_result
            result = protein.would_affect_any_sites(mutation_position)
            assert result == expected_result

    def test_is_preferred_isoform(self):

        proteins = [Protein(refseq='NM_%i' % i) for i in range(5)]
        preferred = proteins[0]
        g = Gene(name='XYZ', isoforms=proteins, preferred_isoform=preferred)
        db.session.add(g)
        db.session.commit()

        # hybrid - python part
        assert preferred.is_preferred_isoform

        # hybrid - sql part
        assert db.session.query(Protein).filter(Protein.is_preferred_isoform).one() == preferred

        for i in range(1, 5):
            assert not proteins[i].is_preferred_isoform
