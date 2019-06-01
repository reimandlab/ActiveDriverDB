from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property

from database import db
from database.types import ScalarSet

from .model import BioModel


class Disease(BioModel):

    # CLNDN: Variant disease name;
    # "ClinVar's preferred disease name for the concept specified by disease identifiers in CLNDISDB"
    name = db.Column(db.String(255), nullable=False, unique=True, index=True)

    # MedGen identifier
    medgen_id = db.Column(db.String(16))

    # OMIM identifier
    omim_id = db.Column(db.Integer)

    # Snomed CT
    snomed_ct_id = db.Column(db.Integer)

    # Orphanet
    orhpanet_id = db.Column(db.String(16))

    # Human_Phenotype_Ontology, e.g. HP:0002145
    hpo_id = db.Column(db.String(16))

    clinvar_types = {
        'Disease',
        'DrugResponse',
        'Finding',
        'PhenotypeInstruction',
        'TraitChoice'
    }

    clinvar_type = db.Column(db.Enum(*clinvar_types))


class ClinicalData(BioModel):

    inherited_id = db.Column(db.Integer, db.ForeignKey('inheritedmutation.id'))

    significance_codes = {
        # TODO: using simple enum might be better
        0: 'Uncertain significance',
        1: 'Not provided',
        2: 'Benign',
        3: 'Likely benign',
        4: 'Likely pathogenic',
        5: 'Pathogenic',
        6: 'Drug response',
        7: 'Histocompatibility',
        255: 'Other',
        # following significances have no mapped ASN.1 terms,
        # thus we will use negative numbers:
        -1: 'Confers sensitivity',
        -2: 'Risk factor',
        -3: 'Association',
        -4: 'Protective',   # TODO?
        -5: 'Affects',
        # following codes are aggregate codes,
        # based on data from multiple submissions
        # these use negative, brginning at -100
        -100: 'Pathogenic/Likely pathogenic',
        -101: 'Benign/Likely benign',
        -102: 'Conflicting interpretations of pathogenicity',
        -103: 'Conflicting data from submitters'
    }
    sig_code = db.Column(db.Integer)

    # secondary annotations of significance
    additional_significances = db.Column(ScalarSet(), default=set)

    # CLNDBN: Variant disease name
    disease_id = db.Column(db.Integer, db.ForeignKey('disease.id'))
    disease = db.relationship('Disease')
    disease_name = association_proxy('disease', 'name')

    @property
    def significance(self):
        return self.significance_codes.get(self.sig_code, None)

    has_significance_conflict = db.Column(db.Boolean, default=False)

    stars_by_status = {
        'practice guideline': 4,
        'reviewed by expert panel': 3,
        'criteria provided, multiple submitters, no conflicts': 2,
        'criteria provided, conflicting interpretations': 1,
        'criteria provided, single submitter': 1,
        'no assertion for the individual variant': 0,
        'no assertion criteria provided': 0,
        'no assertion provided': 0
    }

    # Corresponds to number of starts the entry receives
    # See: https://www.ncbi.nlm.nih.gov/clinvar/docs/review_status/
    # e.g. "practice guideline" - four gold starts
    rev_status = db.Column(db.Enum(*stars_by_status))

    @hybrid_property
    def gold_stars(self):
        return self.stars_by_status.get(self.rev_status, -1)

    def to_json(self, filter=lambda x: x):
        return {
            'Disease': self.disease_name,
            'Significance': self.significance,
            'Status': self.rev_status,
            'Stars': self.gold_stars,
            'VCV': self.variation_id
        }

    significance_subsets = {
        'all': ['Pathogenic', 'Drug response', 'Likely pathogenic', 'Likely benign', 'Benign', 'Uncertain significance', 'Other', 'Not provided'],
        'strict': ['Pathogenic', 'Drug response', 'Likely pathogenic'],
        'not_benign': ['Pathogenic', 'Drug response', 'Likely pathogenic', 'Uncertain significance', 'Other'],
    }

    # ClinVar Variation ID, see PMC5753237 "New and improved VCF files"
    # VCV (Variation in ClinVar) level of aggregation
    # Note: the full VCV identifier is prefixed and padded with zeros:
    # >>> <MeasureSet Type="Variant" ID="216463" Acc="VCV000216463" Version="1">
    # but we only store the actual integer (see "ID" in the example above)
    variation_id = db.Column(db.Integer)


class Cancer(BioModel):
    code = db.Column(db.String(16), unique=True)
    name = db.Column(db.String(64), unique=True)

    def __repr__(self):
        return f'<Cancer with code: {self.code}, named: {self.name}>'
