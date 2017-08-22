from .model_testing import ModelTest
from models import Protein, Site


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
            result = protein.has_sites_in_range(mutation_position - 7, mutation_position + 7)
            assert result == expected_result

