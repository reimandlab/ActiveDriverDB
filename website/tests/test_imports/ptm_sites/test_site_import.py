from types import SimpleNamespace as RawSite

from pandas import DataFrame
from pytest import warns

from database import db, create_key_model_dict
from database_testing import DatabaseTest
from imports.sites.site_importer import SiteImporter
from imports.sites.site_mapper import find_all
from imports.sites.site_mapper import SiteMapper
from models import Protein, Gene


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


def group_by_isoform(sites: DataFrame):
    return {site.refseq: site for site in sites.itertuples(index=False)}


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

    def test_mapping(self):

        gene_a = Gene(name='A', isoforms=[
            # the full isoform of gene A
            Protein(refseq='NM_01', sequence='AAAAAAAAAXAA'),
            # a trimmed isoform of gene A
            Protein(refseq='NM_02', sequence='AAAXAA'),
        ])
        gene_b = Gene(name='B', isoforms=[
            Protein(refseq='NM_03', sequence='BBBBBBBBBYBB'),
            Protein(refseq='NM_04', sequence='BBBYBB'),
        ])
        db.session.add_all([gene_a, gene_b])

        # whoops, NM_03 has be accidentally removed (!)
        db.session.delete(Protein.query.filter_by(refseq='NM_03').one())
        db.session.commit()

        mapper = SiteMapper(
            create_key_model_dict(Protein, 'refseq'),
            lambda s: f'{s.position}{s.residue}'
        )

        sites = DataFrame.from_dict(data={
            'good site A': ('A', 'NM_01', 10, 'AXA', 'X', 1),
            'lost isoform': ('B', 'NM_03', 10, 'BYB', 'Y', 1)
        }, orient='index')

        sites.columns = [
            'gene', 'refseq', 'position', 'sequence', 'residue', 'left_sequence_offset'
        ]

        mapped_sites = mapper.map_sites_by_sequence(sites)
        sites_by_isoform = group_by_isoform(mapped_sites)

        # one from NM_01 (defined), from NM_02 (mapped), from NM_04 (mapped)
        assert len(mapped_sites) == 3
        assert set(sites_by_isoform) == {'NM_01', 'NM_02', 'NM_04'}

        assert sites_by_isoform['NM_01'].residue == sites_by_isoform['NM_02'].residue == 'X'
        assert sites_by_isoform['NM_01'].position == 10
        assert sites_by_isoform['NM_02'].position == 4

        assert sites_by_isoform['NM_04'].residue == 'Y'
        assert sites_by_isoform['NM_04'].position == 4

        # will the mapping to NM_02 still work if we remove 'gene' column?
        sites.drop(columns=['gene'], inplace=True)
        mapped_sites = mapper.map_sites_by_sequence(sites)
        sites_by_isoform = group_by_isoform(mapped_sites)

        assert len(mapped_sites) == 2
        assert set(sites_by_isoform) == {'NM_01', 'NM_02'}
