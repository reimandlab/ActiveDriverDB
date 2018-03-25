from database import db

from .model import BioModel
from .model import make_association_table
from .sites import SiteType


class Kinase(BioModel):
    """Kinase represents an entity interacting with some site.

    The protein linked to a kinase is chosen as the `preferred_isoform` of a
    gene having the same name as given kinase (since we do not have specific
    refseq identifiers for a single kinase).
    Not every kinase has an associated protein.
    """
    name = db.Column(db.String(80), unique=True, index=True)
    protein_id = db.Column(db.Integer, db.ForeignKey('protein.id'))
    group_id = db.Column(db.Integer, db.ForeignKey('kinasegroup.id'))

    site_type_table = make_association_table('kinase.id', SiteType.id)
    is_involved_in = db.relationship(
        SiteType,
        secondary=site_type_table,
        collection_class=set,
        backref='kinases'
    )

    def __repr__(self):
        return f'<Kinase {self.name} belonging to {self.group} group>'

    @property
    def mutations(self):
        if not self.protein:
            return tuple()
        return self.protein.mutations.all()

    def to_json(self):
        return {
            'name': self.name,
            'protein': {
                'refseq': self.protein.refseq
            } if self.protein else None
        }


class KinaseGroup(BioModel):
    """Kinase group is the only grouping of kinases currently in use.

    The nomenclature may differ across sources and a `group` here
    may be equivalent to a `family` in some publications / datasets.
    """
    name = db.Column(db.String(80), unique=True, index=True)
    kinases = db.relationship(
        'Kinase',
        order_by='Kinase.name',
        backref='group'
    )

    site_type_table = make_association_table('kinasegroup.id', SiteType.id)
    is_involved_in = db.relationship(
        SiteType,
        secondary=site_type_table,
        collection_class=set,
        backref='kinase_groups'
    )

    def __repr__(self):
        return f'<KinaseGroup {self.name}, with {len(self.kinases)} kinases>'
