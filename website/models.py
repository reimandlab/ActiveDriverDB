from app import db
from sqlalchemy import func
from sqlalchemy.sql import exists
from sqlalchemy import and_


class Protein(db.Model):
    __tablename__ = 'protein'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True)
    refseq = db.Column(db.String(32), unique=True)
    sequence = db.Column(db.Text)
    disorder_map = db.Column(db.Text)
    sites = db.relationship('Site', order_by='Site.position')
    mutations = db.relationship('Mutation')

    def __init__(self, name):
        self.name = name
        self.sequence = ''
        self.disorder_map = ''

    def __repr__(self):
        return '<Protein %r>' % self.name

    @property
    def length(self):
        return len(self.sequence)

    @property
    def mutations_grouped(self):

        mutations_grouped = {}
        for mutation in self.mutations:
            # for now, I am grouping just by position and cancer

            key = (mutation.position,
                   mutation.mut_residue,
                   Cancer.query.get(mutation.cancer_type).name)
            try:
                mutations_grouped[key] += [mutation]
            except KeyError:
                mutations_grouped[key] = [mutation]
        return mutations_grouped

    @property
    def disorder_regions(self):
        """Transform binary disorder data into list of spans.

        Each span is represented by a tuple: (start, length)"""

        disorder_regions = []
        inside_region = False

        for i in range(len(self.disorder_map)):
            residue = int(self.disorder_map[i])
            if inside_region:
                if not residue:
                    inside_region = False
                    disorder_regions[-1][1] = i - disorder_regions[-1][0]
            else:
                if residue:
                    disorder_regions += [[i, 1]]
                    inside_region = True

        return disorder_regions


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


class Cancer(db.Model):
    __tablename__ = 'cancer'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(16))
    name = db.Column(db.Text)

    def __init__(self, code, name):
        self.code = code
        self.name = name


class Mutation(db.Model):
    __tablename__ = 'mutation'
    id = db.Column(db.Integer, primary_key=True)
    gene_id = db.Column(db.Integer, db.ForeignKey('protein.id'))
    position = db.Column(db.Integer)
    wt_residue = db.Column(db.String(1))
    mut_residue = db.Column(db.String(1))
    cancer_type = db.Column(db.Integer, db.ForeignKey('cancer.id'))
    sample_id = db.Column(db.String(64))

    def __init__(self, gene_id, cancer, sample_id,
                 position, wt_residue, mut_residue):
        self.gene_id = gene_id
        self.cancer_type = cancer
        self.sample_id = sample_id
        self.position = position
        self.wt_residue = wt_residue
        self.mut_residue = mut_residue

    # Note: following properties could become a columns of the database tables
    # (in the future) to avoid repetitive calculation of constant variables.
    # Nonetheless making decision about each of these should take into account,
    # how often columns and other models referenced in property will be updated
    # (so we can avoid unnecessary whole database rebuilding).

    @property
    def is_ptm(self):
        """Mutation is PTM related if it may affect PTM site.

        Mutations flanking PTM site in a distance up to 7 residues from
        a site (called here 'distal') will be included too.
        """
        return self.is_ptm_distal

    @property
    def is_ptm_direct(self):
        """True if the mutation is on the same position as some PTM site."""
        return db.session.query(
            exists().where(and_(Site.gene_id == self.gene_id,
                                Site.position == self.position))
            ).scalar()

    @property
    def is_ptm_proximal(self):
        """Check if the mutation is in close proximity of some PTM site.

        Proximity is defined here as [pos - 3, pos + 3] span,
        where pos is the position of a PTM site.
        """
        position = self.position
        q = exists().where(
            and_(
                Site.gene_id == self.gene_id,
                Site.position.between(position - 4, position + 4)
                )
        )
        return db.session.query(q).scalar()

    @property
    def is_ptm_distal(self):
        """Check if the mutation is distal flanking mutation of some PTM site.

        Distal flank is defined here as [pos - 7, pos + 7] span,
        where pos is the position of a PTM site.
        """
        position = self.position
        q = exists().where(
            and_(
                Site.gene_id == self.gene_id,
                Site.position.between(position - 8, position + 8)
                )
        )
        return db.session.query(q).scalar()

    @property
    def cnt_ptm_affected(self):
        """How many PTM sites might be affected by this mutation,

        when taking into account -7 to +7 spans of each PTM site.
        """
        pos = self.position
        count = db.session.query(func.count(Site.id)).\
            filter_by(gene_id=self.gene_id).\
            filter(Site.position.between(pos - 8, pos + 8)).scalar()

        return count

    @property
    def impact_on_ptm(self):
        """How intense might be impact of the mutation on the closest PTM site.

        Possible values are: 'direct', 'proximal', or 'diastal'. Those
        properties are based on the distance measurement to closest PTM site
        """
        if self.is_ptm_direct:
            return 'direct'
        if self.is_ptm_proximal:
            return 'proximal'
        if self.is_ptm_distal:
            return 'distal'
        return None
