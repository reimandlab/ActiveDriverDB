import re
from functools import lru_cache

from pathlib import Path
from sqlalchemy import func
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method

from database import db, client_side_defaults
from database.functions import greatest, least
from database.types import ScalarSet
from exceptions import ValidationError
from helpers.plots import sequence_logo

from .model import BioModel, make_association_table


cache_store = []


def cache(func):
    decorated = lru_cache()(func)
    cache_store.append(decorated)
    return decorated


def clear_cache():
    for cached in cache_store:
        cached.cache_clear()


class SiteType(BioModel):
    # this table can be pre-fetched into the application
    # memory on start, as it is not supposed to change after
    # the initial import
    name = db.Column(db.String(16), unique=True)

    def find_modified_residues(self) -> set:
        return {site.residue for site in self.sites}

    def filter(self, query):
        return query.filter(Site.types.contains(self))

    def __str__(self):
        return self.name

    @classmethod
    def available_types(cls, include_any=False):
        return [site_type for site_type in cls.query] + (
            [AnySiteType()]
            if include_any else
            []
        )

    @classmethod
    @cache
    def id_by_name(cls):
        return {
            site_type.name: site_type.id
            for site_type in cls.available_types()
        }

    @classmethod
    @cache
    def type_by_id(cls):
        return {
            site_type.id: site_type
            for site_type in cls.available_types()
        }

    @classmethod
    def fuzzy_filter(cls, other_type, join=False, site=None):
        site = site if site is not None else Site

        matched_types_ids = [
            type_id
            for type_name, type_id in cls.id_by_name().items()
            if other_type.name in type_name
        ]

        if len(matched_types_ids) == 1:
            if not join:
                return SiteType.id == matched_types_ids[0]
            return site.types.contains(cls.type_by_id()[matched_types_ids[0]])

        return site.types.any(
            SiteType.id.in_(matched_types_ids)
        )
        # NB: there are following alternatives available:
        # return Site.types.contains(matched_types[0]) # for single type matched
        # return or_(Site.types.any(id=site_type.id) for site_type in matched_types)
        # return Site.types.any(SiteType.name.like('%' + other_site.name + '%'))

    @classmethod
    def fuzzy_comparator(cls, other_types, some_type):

        if other_types is some_type:
            return

        matched_types_ids = [
            type_id
            for type_name, type_id in cls.id_by_name().items()
            if some_type.name in type_name
        ]

        return any(other_type.id in matched_types_ids for other_type in other_types)

    @property
    def sub_types(self):
        return [
            type_name
            for type_name, type_id in self.id_by_name().items()
            if self.name in type_name and type_name != self.name
        ]


class AnySiteType:

    name = ''
    id = None

    @staticmethod
    def filter(query):
        return query

    def __str__(self):
        return ''


def default_residue(context):
    from .protein import Protein

    if not hasattr(context, 'current_parameters'):
        return
    params = context.current_parameters

    protein = params.get('protein')
    protein_id = params.get('protein_id')

    if not protein and protein_id:
        protein = Protein.query.get(protein_id)

    position = params.get('position')

    if protein and position:
        try:
            return protein.sequence[position - 1]
        except IndexError:
            print('Position of PTM possibly exceeds its protein')
            return


class SiteSource(BioModel):
    name = db.Column(db.String(16), unique=True)


def extract_padded_sequence(protein: 'Protein', left: int, right: int):
    return (
        '-' * -min(0, left) +
        protein.sequence[max(0, left):min(right, protein.length)] +
        '-' * max(0, right - protein.length)
    )


class DataError(Exception):
    pass


class Site(BioModel):

    # Note: this position is 1-based
    position = db.Column(db.Integer, index=True)

    residue = db.Column(db.String(1), default=default_residue)

    pmid = db.Column(ScalarSet(separator=',', element_type=int), default=set)

    site_type_table = make_association_table('site.id', SiteType.id, index=True)
    types = db.relationship(SiteType, secondary=site_type_table, backref='sites', collection_class=set)

    @property
    def types_names(self):
        return {site_type.name for site_type in self.types}

    protein_id = db.Column(db.Integer, db.ForeignKey('protein.id'))

    sources = db.relationship(
        'SiteSource',
        secondary=make_association_table('site.id', SiteSource.id),
        collection_class=set,
        backref='sites'
    )
    kinases = db.relationship(
        'Kinase',
        secondary=make_association_table('site.id', 'kinase.id'),
        collection_class=set,
        backref='sites'
    )
    kinase_groups = db.relationship(
        'KinaseGroup',
        secondary=make_association_table('site.id', 'kinasegroup.id'),
        collection_class=set,
        backref='sites'
    )

    @client_side_defaults('pmid')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.validate_position()
        self.validate_residue()

    def get_nearby_sequence(self, offset=3):
        # self.position is 1-based
        return extract_padded_sequence(self.protein, self.position - offset - 1, self.position + offset)

    @hybrid_property
    def sequence(self):
        return self.get_nearby_sequence(offset=7)

    @sequence.expression
    def sequence(cls):
        """Required joins: Protein"""
        from .protein import Protein

        # SQL is 1 based
        left = cls.position - 8

        sequence = func.substr(
            Protein.sequence,
            greatest(cls.position - 7, 1),
            least(
                15 + least(left, 0),
                func.length(Protein.sequence) - left
            )
        )
        left_padding = func.substr('-------', 1, greatest(-left, 0))
        right_padding = func.substr('-------', 1, greatest(
            cls.position + 8 - func.length(Protein.sequence), 0)
        )
        return left_padding.concat(sequence).concat(right_padding)

    @hybrid_property
    def in_disordered_region(self):
        try:
            return self.protein.disorder_map[self.position - 1] == '1'
        except IndexError:
            raise DataError(f"Disorder of {self.protein} does not include {self.position}")

    @in_disordered_region.expression
    def in_disordered_region(cls):
        """Required joins: Protein"""
        from .protein import Protein

        disorder = func.substr(
            Protein.disorder_map,
            cls.position,    # both: SQL and self.position are 1-based
            1
        )

        return disorder == '1'

    @hybrid_method
    def has_motif(self, motif):
        return re.match(motif, self.sequence)

    @has_motif.expression
    def has_motif(cls, motif):
        """Required joins: Protein"""
        return cls.sequence.op('regexp')(motif)

    @hybrid_property
    def mutations(self):
        return [
            {
                'ref': mutation.ref,
                'pos': mutation.position,
                'alt': mutation.alt,
                'impact': mutation.impact_on_specific_ptm(self)
            }
            for mutation in self.protein.mutations
            if abs(mutation.position - self.position) < 7
        ]

    affected_by_mutations = db.relationship(
        'Mutation',
        primaryjoin=(
            'and_('
            '   Site.protein_id == foreign(Mutation.protein_id),'
            '   Mutation.position.between(Site.position - 7, Site.position + 7)'
            ')'
        )
    )

    @mutations.expression
    def mutations(self):
        return self.affected_by_mutations

    def validate_position(self):
        position = self.position
        if self.protein:
            if position > self.protein.length or position < 1:
                raise ValidationError(
                    'Site is placed outside of protein sequence '
                    '(position: {0}, protein length: {1}) '
                    'for {2} at position: {3}'.format(
                        position, self.protein.length,
                        self.protein.refseq, self.position
                    )
                )

    def validate_residue(self):
        residue = self.residue
        if residue and self.protein and self.position:
            deduced_residue = self.protein.sequence[self.position - 1]
            if self.residue != deduced_residue:
                raise ValidationError(
                    'Site residue {0} does not match '
                    'the one from protein sequence ({1}) '
                    'for {2} at position: {3}'.format(
                        residue, deduced_residue,
                        self.protein.refseq, self.position
                    )
                )

    def __repr__(self):
        return '<Site of protein: {0}, at pos: {1}>'.format(
            self.protein.refseq if self.protein else '-',
            self.position
        )

    def to_json(self, with_kinases=False):
        data = {
            'position': self.position,
            'type': ','.join(self.types_names),
            'residue': self.residue
        }
        if with_kinases:
            data['kinases'] = [
                kinase.to_json()
                for kinase in self.kinases
            ]
            data['kinase_groups'] = [
                {'name': group.name}
                for group in self.kinase_groups
            ]
        return data


class SiteMotif(BioModel):
    name = db.Column(db.String(32))
    pattern = db.Column(db.String(32))

    site_type_id = db.Column(db.Integer, db.ForeignKey('sitetype.id'))
    site_type = db.relationship(SiteType, backref='motifs')

    def generate_pseudo_logo(self, sequences):
        path = self.pseudo_logo_path
        sequence_logo(sequences, path=path, title=self.name)

    @property
    def pseudo_logo_path(self) -> Path:
        path = Path('static/logos/')
        path.mkdir(parents=True, exist_ok=True)

        safe_name = ''.join(c for c in self.name if c.isalnum())
        path /= f'{safe_name}_{self.id}.svg'

        return path
