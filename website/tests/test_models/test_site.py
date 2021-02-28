import pytest
from database import db, get_engine
from .model_testing import ModelTest

from exceptions import ValidationError
from models import Protein, SiteType
from models import Site


def load_regex_support(engine):
    if engine.name == 'sqlite':
        engine.raw_connection().enable_load_extension(True)
        engine.execute('select load_extension("/usr/lib/sqlite3/pcre.so")')


class SiteTest(ModelTest):

    def test_consistency(self):

        methylation = SiteType(name='methylation')

        p = Protein(refseq='NM_007', id=1, sequence='ABCD')
        db.session.add(p)

        # matching residue (note: for sites, positions are 1-based)
        assert Site(position=2, types={methylation}, residue='B', protein=p)

        # mismatched residue
        with pytest.raises(ValidationError):
            Site(position=3, types={methylation}, residue='B', protein=p)

        # no residue and position in range
        assert Site(position=2, protein=p)

        # no residue and position outside of range
        with pytest.raises(ValidationError):
            Site(position=5, protein=p)
        with pytest.raises(ValidationError):
            Site(position=-5, protein=p)

    def test_default_residue(self):
        p = Protein(refseq='NM_007', id=1, sequence='ABCD')

        methylation = SiteType(name='methylation')

        # note: for sites, positions are 1-based)
        site = Site(position=2, types={methylation}, protein=p)

        db.session.add(p)
        db.session.commit()

        assert site.residue == 'B'

    def test_gather_residues(self):
        methylation = SiteType(name='methylation')

        p = Protein(refseq='NM_007', id=1, sequence='ABCD')
        sites = [
            Site(position=2, types={methylation}, protein=p),  # default -> 'B'
            Site(position=4, types={methylation}, residue='D'),
        ]
        db.session.add_all(sites)
        db.session.commit()

        assert methylation.find_modified_residues() == {'B', 'D'}

    def test_sequence(self):
        methylation = SiteType(name='methylation')

        p = Protein(refseq='NM_007', id=1, sequence='ABCDEFGHIJKLMNOPQRSTUVWXYZ')
        db.session.add(p)

        data = {
            0: '-------ABCDEFGH',
            10: 'DEFGHIJKLMNOPQR',
            25: 'STUVWXYZ-------'
        }

        sites = {}

        for position in data:
            sites[position] = Site(position=position + 1, types={methylation}, residue=p.sequence[position], protein=p)

        db.session.add_all(sites.values())
        db.session.commit()

        for position, expected_sequence in data.items():
            site = sites[position]
            # Python side
            assert site.sequence == expected_sequence
            # SQL side
            assert Site.query.filter_by(sequence=expected_sequence).one() == site

        sequences = [s for (s, ) in db.session.query(Site.sequence).select_from(Site).join(Protein)]
        assert set(sequences) == set(data.values())

    def test_in_disordered(self):
        methylation = SiteType(name='methylation')

        p = Protein(
            refseq='NM_007', id=1,
            disorder_map='10000000001000000000000001',
            sequence='ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        )
        db.session.add(p)

        sites_in_disordered = {0, 10, 25}
        sites_not_disordered = {1, 9, 11, 24}

        sites = {}

        for position in sites_in_disordered | sites_not_disordered:
            print(position)
            print(len(p.sequence[position]))
            sites[position] = Site(position=position + 1, types={methylation}, residue=p.sequence[position], protein=p)

        # Python side

        for position in sites_in_disordered:
            site = sites[position]
            assert site.in_disordered_region

        for position in sites_not_disordered:
            site = sites[position]
            assert not site.in_disordered_region

        # SQL side
        assert {site.position - 1 for site in Site.query.filter_by(in_disordered_region=True)} == sites_in_disordered
        assert {site.position - 1 for site in Site.query.filter_by(in_disordered_region=False)} == sites_not_disordered

    def test_has_motif(self):

        engine = get_engine('bio')
        load_regex_support(engine)

        p = Protein(refseq='NM_007', id=1, sequence='ABCDEFGHIJKLMNOPQRSTUVWXYZ')
        s = Site(position=3, residue='C', protein=p)

        db.session.add(s)
        db.session.commit()

        # Python side
        assert s.has_motif('.{7}C[DX].{6}')
        assert not s.has_motif('.{7}C[XY].{6}')

        # SQL side
        assert Site.query.filter(Site.has_motif('.{7}C[DX].{6}')).one()
        assert not Site.query.filter(Site.has_motif('.{7}C[XY].{6}')).all()

    def test_types(self):
        methylation = SiteType(name='methylation')

        p = Protein(refseq='NM_007', id=1, sequence='ABCD')
        db.session.add(p)

        site = Site(position=2, types={methylation}, residue='B', protein=p)
        db.session.add(site)

        db.session.commit()

        query = Protein.query

        assert query.filter(Protein.sites.any(Site.types.contains(methylation))).one()
        assert not query.filter(Protein.sites.any(~Site.types.contains(methylation))).all()
        assert Site.query.filter(Site.types.contains(methylation)).count() == 1
        assert not Site.query.filter(~Site.types.contains(methylation)).all()

        phosphorylation = SiteType(name='phosphorylation')
        assert not query.filter(Protein.sites.any(Site.types.contains(phosphorylation))).all()
        assert query.filter(Protein.sites.any(~Site.types.contains(phosphorylation))).one()
        assert Site.query.filter(Site.types.contains(phosphorylation)).count() == 0
