from sqlalchemy.ext.associationproxy import association_proxy

from database import db

from .model import BioModel


class Disease(BioModel):

    # CLNDBN: Variant disease name
    name = db.Column(db.String(255), nullable=False, unique=True, index=True)


class ClinicalData(BioModel):

    inherited_id = db.Column(db.Integer, db.ForeignKey('inheritedmutation.id'))

    significance_codes = {
        0: 'Uncertain significance',
        1: 'Not provided',
        2: 'Benign',
        3: 'Likely benign',
        4: 'Likely pathogenic',
        5: 'Pathogenic',
        6: 'Drug response',
        7: 'Histocompatibility',
        255: 'Other'
    }

    # CLNSIG: Variant Clinical Significance:
    sig_code = db.Column(db.Integer)

    # CLNDBN: Variant disease name
    disease_id = db.Column(db.Integer, db.ForeignKey('disease.id'))
    disease = db.relationship('Disease')
    disease_name = association_proxy('disease', 'name')

    @property
    def significance(self):
        return self.significance_codes.get(self.sig_code, None)

    # CLNREVSTAT: ?
    # no_assertion - No assertion provided,
    # no_criteria - No assertion criteria provided,
    # single - Criteria provided single submitter,
    # mult - Criteria provided multiple submitters no conflicts,
    # conf - Criteria provided conflicting interpretations,
    # exp - Reviewed by expert panel,
    # guideline - Practice guideline
    rev_status = db.Column(db.Text)

    def to_json(self, filter=lambda x: x):
        return {
            'Disease': self.disease_name,
            'Significance': self.significance,
            'Review status': self.rev_status
        }

    significance_subsets = {
        'all': ['Pathogenic', 'Drug response', 'Likely pathogenic', 'Likely benign', 'Benign', 'Uncertain significance', 'Other', 'Not provided'],
        'strict': ['Pathogenic', 'Drug response', 'Likely pathogenic'],
        'not_benign': ['Pathogenic', 'Drug response', 'Likely pathogenic', 'Uncertain significance', 'Other'],
    }


class Cancer(BioModel):
    code = db.Column(db.String(16), unique=True)
    name = db.Column(db.String(64), unique=True)

    def __repr__(self):
        return f'<Cancer with code: {self.code}, named: {self.name}>'
