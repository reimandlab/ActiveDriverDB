from types import SimpleNamespace as RawSite

from pytest import warns

from database import db
from database_testing import DatabaseTest
from imports.sites.site_importer import SiteImporter
from imports.sites.site_mapper import find_all
from imports.sites.site_mapper import SiteMapper
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


def create_importer(*args, offset=7, **kwargs):

    class MinimalSiteImporter(SiteImporter):

        source_name = 'DummySource'
        site_offset = offset

        def load_sites(self, *args, **kwargs):
            return []

        site_types = []

    return MinimalSiteImporter(*args, **kwargs)


class TestImport(DatabaseTest):

    def test_extract_sequence_and_offset(self):
        protein = Protein(refseq='NM_0001', sequence='MSSSGTPDLPVLLTDLKIQYTKIFINNEWHDSVSGK')
        db.session.add(protein)

        importer = create_importer(offset=7)

        cases = [
            [RawSite(position=2, refseq='NM_0001', residue='S'), 'MSSSGTPDL', 1],
            [RawSite(position=10, refseq='NM_0001', residue='P'), 'SSGTPDLPVLLTDLK', 7]
        ]

        for site, sequence, offset in cases:
            assert importer.extract_site_surrounding_sequence(site) == sequence
            assert importer.determine_left_offset(site) == offset

    def test_map_site_to_isoform(self):

        mapper = SiteMapper([], lambda s: f'{s.position}{s.sequence}')

        site = RawSite(sequence='FIN', position=6, left_sequence_offset=1)
        protein = Protein(sequence='LKIQYTKIFINNEWHDSVSG')

        assert mapper.map_site_to_isoform(site, protein) == [10]

        with warns(UserWarning, match='More than one match for: 2KI'):
            site = RawSite(sequence='KI', position=2, left_sequence_offset=0)
            assert mapper.map_site_to_isoform(site, protein) == [2, 7]
