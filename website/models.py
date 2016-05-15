from app import db


class Protein(db.Model):
    __tablename__ = 'protein'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True)
    refseq = db.Column(db.String(32), unique=True)
    sequence = db.Column(db.Text)
    disorder_map = db.Column(db.Text)
    sites = db.relationship('Site')
    mutations = db.relationship('Mutation')

    def __init__(self, name):
        self.name = name
        self.sequence = ''
        self.disorder_map = ''

    def __repr__(self):
        return '<Protein %r>' % self.name


class Site(db.Model):
    __tablename__ = 'site'
    id = db.Column(db.Integer, primary_key=True)
    gene_id = db.Column(db.Integer, db.ForeignKey('protein.id'))
    position = db.Column(db.Integer)
    residue = db.Column(db.String(1))
    kinase = db.Column(db.Text)
    pmid = db.Column(db.String(32))

    def __init__(self, gene_id, position, residue, kinase, pmid):
        self.gene_id = gene_id
        self.position = position
        self.residue = residue
        self.kinase = kinase
        self.pmid = pmid


class Mutation(db.Model):
    __tablename__ = 'mutation'
    id = db.Column(db.Integer, primary_key=True)
    gene_id = db.Column(db.Integer, db.ForeignKey('protein.id'))
    position = db.Column(db.Integer)
    wt_residue = db.Column(db.String(1))
    mut_residue = db.Column(db.String(1))
    cancer_type = db.Column(db.String(32))
    sample_id = db.Column(db.String(64))

    def __init__(self, gene_id, cancer_type, sample_id, position, wt_residue, mut_residue):
        self.gene_id = gene_id
        self.cancer_type = cancer_type
        self.sample_id = sample_id
        self.position = position
        self.wt_residue = wt_residue
        self.mut_residue = mut_residue
