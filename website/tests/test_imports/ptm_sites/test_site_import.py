from collections import namedtuple

from pytest import warns

from database_testing import DatabaseTest
from imports.sites.site_importer import find_all, map_site_to_isoform
from models import Protein


def test_find_all():

    background = 'Lorem ipsum dololor'

    cases = {
        'L': [0],
        'o': [1, 13, 15, 17],
        'olo': [13, 15]
    }

    for query, expected_result in cases.items():
        assert find_all(background, query) == expected_result


class TestImport(DatabaseTest):

    def test_map_site_to_isoform(self):

        RawSite = namedtuple('RawSite', 'sequence position')

        site = RawSite(sequence='FIN', position=6)
        protein = Protein(sequence='LKIQYTKIFINNEWHDSVSG')

        assert map_site_to_isoform(site, protein) == [8]

        with warns(UserWarning):
            site = RawSite(sequence='KI', position=2)
            assert map_site_to_isoform(site, protein) == [1, 6]
