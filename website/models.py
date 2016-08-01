from database import db
from sqlalchemy import and_
from sqlalchemy import func
from sqlalchemy.sql import exists, select
from sqlalchemy.ext.hybrid import hybrid_method
from sqlalchemy.ext.hybrid import hybrid_property
from werkzeug.utils import cached_property


def make_association_table(fk1, fk2):
    """Create an association table basing on names of two given foreign keys.

    From keys: `site.id` and `kinase.id` a table named: site_kinase_association
    will be created and it will contain two columns: `site_id` and `kinase_id`.
    """
    table_name = '%s_%s_association' % (fk1.split('.')[0], fk2.split('.')[0])
    return db.Table(
        table_name, db.metadata,
        db.Column(fk1.replace('.', '_'), db.Integer, db.ForeignKey(fk1)),
        db.Column(fk2.replace('.', '_'), db.Integer, db.ForeignKey(fk2)),
    )


class Kinase(db.Model):
    """Kinase represents an entity interacting with some site.

    The protein linked to a kinase is chosen as the `preferred_isoform` of a
    gene having the same name as given kinase (since we do not have specific
    refseq identificator for a single kinase).
    Not every kinase has an associated protein.
    """
    __tablename__ = 'kinase'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, index=True)
    protein_id = db.Column(db.Integer, db.ForeignKey('protein.id'))
    group_id = db.Column(db.Integer, db.ForeignKey('kinase_group.id'))

    def __repr__(self):
        return '<Kinase {0} belonging to {1} group>'.format(
            self.name,
            self.group
        )


class KinaseGroup(db.Model):
    """Kinase group is the only grouping of kinases currently in use.

    The nomenclature may differ across sources and a `group` here
    may be equivalent to a `family` in some publications / datasets.
    """
    __tablename__ = 'kinase_group'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, index=True)
    kinases = db.relationship(
        'Kinase',
        order_by='Kinase.name',
        backref='group'
    )

    def __repr__(self):
        return '<KinaseGroup {0}, with {1} kinases>'.format(
            self.name,
            len(self.kinases)
        )


class Gene(db.Model):
    """Gene is uniquely identified although has multiple protein isoforms.

    The isoforms are always located on the same chromsome, strand and are
    a product of the same gene. The major function of this model is to group
    isoforms classified as belonging to the same gene and to verify
    consistency of chromsomes and strands information across the database.
    """
    __tablename__ = 'gene'

    id = db.Column(db.Integer, primary_key=True)

    # HGNC symbols are allowed to be varchar(255) but 40 is still safe
    # as for storing symbols that are currently in use. Let's use 2 x 40.
    name = db.Column(db.String(80), unique=True, index=True)

    # TRUE represent positive (+) strand, FALSE represents negative (-) strand
    # As equivalent to (?) from Generic Feature Format NULL could be used.
    strand = db.Column(db.Boolean())

    # Chromosome - up to two digits (1-22 inclusive), X and Y and eventually MT
    chrom = db.Column(db.CHAR(2))

    isoforms = db.relationship(
        'Protein',
        backref='gene',
        foreign_keys='Protein.gene_id'
    )

    preferred_isoform_id = db.Column(
        db.Integer,
        db.ForeignKey('protein.id', name='fk_preferred_isoform')
    )
    preferred_isoform = db.relationship(
        'Protein',
        uselist=False,
        foreign_keys=preferred_isoform_id,
        post_update=True
    )

    @cached_property
    def alternative_isoforms(self):
        return [
            isoform
            for isoform in self.isoforms
            if isoform.id != self.preferred_isoform_id
        ]

    def __repr__(self):
        return '<Gene {0}, with {1} isoforms>'.format(
            self.name,
            len(self.isoforms)
        )


class Protein(db.Model):
    """Protein represents a single isoform of a product of given gene."""
    __tablename__ = 'protein'

    id = db.Column(db.Integer, primary_key=True)

    gene_id = db.Column(db.Integer, db.ForeignKey('gene.id'))

    # refseq id of mRNA sequence (always starts with 'NM_')
    # HGNC reserves up to 50 characters; 32 seems good enough but
    # I did not found any technical documentation; useful resource:
    # ncbi.nlm.nih.gov/books/NBK21091/
    refseq = db.Column(db.String(32), unique=True, index=True)

    # sequence of amino acids represented by one-letter IUPAC symbols
    sequence = db.Column(db.Text, default='')

    # sequence of ones and zeros where ones indicate disorder region
    # should be no longer than the sequence (defined above)
    disorder_map = db.Column(db.Text, default='')

    # transcription start/end coordinates
    tx_start = db.Column(db.Integer)
    tx_end = db.Column(db.Integer)

    # coding sequence domain start/end coordinates
    cds_start = db.Column(db.Integer)
    cds_end = db.Column(db.Integer)

    sites = db.relationship(
        'Site',
        order_by='Site.position',
        backref='protein'
    )
    mutations = db.relationship(
        'Mutation',
        order_by='Mutation.position',
        lazy='dynamic',
        backref='protein'
    )
    domains = db.relationship(
        'Domain',
        backref='protein'
    )
    kinase = db.relationship(
        'Kinase',
        backref='protein'
    )

    def __init__(self, **kwargs):
        for key in ('sequence', 'disorder_map'):
            if key not in kwargs:
                kwargs[key] = ''

        super().__init__(**kwargs)

    def __repr__(self):
        return '<Protein {0} with seq of {1} aa from {2} gene>'.format(
            self.refseq,
            self.length,
            self.gene.name
        )

    @cached_property
    def is_preferred_isoform(self):
        return self.gene.preferred_isoform == self

    @cached_property
    def length(self):
        """Length of protein's sequence"""
        return len(self.sequence)

    @cached_property
    def mutations_grouped(self):
        """Mutations grouped by cancer type and position in the sequence"""
        mutations_grouped = {}
        for mutation in self.mutations:
            # for now, I am grouping just by position and cancer

            key = (mutation.position,
                   mutation.mut_residue,
                   mutation.cancer.name)
            try:
                mutations_grouped[key] += [mutation]
            except KeyError:
                mutations_grouped[key] = [mutation]
        return mutations_grouped

    @cached_property
    def disorder_length(self):
        """How many reidues are disordered."""
        return sum([int(residue) for residue in self.disorder_map])

    @cached_property
    def disorder_regions(self):
        """Transform binary disorder data into list of spans.

        Each span is represented by a tuple: (start, length).
        The coordinates are 1-based.
        """

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
                    disorder_regions += [[i + 1, 1]]
                    inside_region = True

        return disorder_regions

    @hybrid_property
    def kinases(self):
        """Get all kinases associated with this protein"""
        kinases = set()
        # first of all we need kinases to be a foreign key to proteins
        for site in self.sites:
            kinases.update((site.kinases))
        return kinases

    @kinases.expression
    def kinases(self):
        """SQL expression for kinases"""
        q = select(Protein.sites.kinases).\
            distinct()
        return db.session.query(q)

    @hybrid_property
    def kinase_groups(self):
        """Get all kinase_groups associated with this protein"""
        kinase_groups = set()
        for site in self.sites:
            kinase_groups.update((site.kinase_groups))
        return kinase_groups


class Site(db.Model):
    __tablename__ = 'site'
    id = db.Column(db.Integer, primary_key=True)
    position = db.Column(db.Integer, index=True)
    residue = db.Column(db.String(1))
    pmid = db.Column(db.Text)
    type = db.Column(db.Text)
    protein_id = db.Column(db.Integer, db.ForeignKey('protein.id'))
    kinases = db.relationship(
        'Kinase',
        secondary=make_association_table('site.id', 'kinase.id')
    )
    kinase_groups = db.relationship(
        'KinaseGroup',
        secondary=make_association_table('site.id', 'kinase_group.id')
    )

    def __repr__(self):
        return '<Site of protein: {0}, at pos: {1}>'.format(
            Protein.query.get(self.protein_id).name,
            self.position
        )


class Cancer(db.Model):
    __tablename__ = 'cancer'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(16))
    name = db.Column(db.Text)
    mutations = db.relationship('Mutation', backref='cancer')

    def __repr__(self):
        return '<Cancer with code: {0}, named: {1}>'.format(
            self.code,
            self.name
        )


class InterproDomain(db.Model):
    __tablename__ = 'interpro_domain'
    id = db.Column(db.Integer, primary_key=True)

    # Interpro ID
    accession = db.Column(db.Text)

    # Interpro Short Description
    short_description = db.Column(db.Text)

    # Interpro Description
    description = db.Column(db.Text)

    occurrences = db.relationship('Domain', backref='interpro')

    @cached_property
    def possible_names(self):
        """Return strings which might be used to describe the domain,

        form the longest to the shortest. Last one has to be a single character
        """
        return [
            self.accession + ': ' + self.description,
            self.accession + ': ' + self.short_description,
            self.accession,
            self.description[0] + '.',  # TODO this is not informative... :(
            self.description[0]
        ]


class Domain(db.Model):
    __tablename__ = 'domain'
    id = db.Column(db.Integer, primary_key=True)
    protein_id = db.Column(db.Integer, db.ForeignKey('protein.id'))
    interpro_id = db.Column(db.Integer, db.ForeignKey('interpro_domain.id'))

    start = db.Column(db.Integer)
    end = db.Column(db.Integer)

    @cached_property
    def shown_name(self):
        """Generates a name for the domain which will fit into a track."""
        names_to_try = self.interpro.possible_names
        length = self.end - self.start
        for name in names_to_try:
            if len(name) <= length:
                return name

        # the last name to try is one character long, and domains cannot be
        # shorter than one aminoacid (or: certainly they have to be longer)
        assert False

    def __len__(self):
        return self.end - self.start


class Mutation(db.Model):
    __tablename__ = 'mutation'
    id = db.Column(db.Integer, primary_key=True)
    position = db.Column(db.Integer)
    wt_residue = db.Column(db.String(1))
    mut_residue = db.Column(db.String(1))
    sample_id = db.Column(db.String(64))
    cancer_id = db.Column(db.Integer, db.ForeignKey('cancer.id'))
    protein_id = db.Column(db.Integer, db.ForeignKey('protein.id'))

    pwm = db.Column(db.Text)
    pwm_family = db.Column(db.Text)

    # gain = +1, loss = -1
    effect = db.Column(db.Boolean)

    # one mutation can affect multiple sites and
    # one site can be affected by multiple mutations
    sites = db.relationship(
        'Site',
        secondary=make_association_table('site.id', 'mutation.id')
    )

    # not null only for mimp mutations:
    # position of a mutation in an associated motif
    position_in_motif = db.Column(db.Integer)

    # Note: following properties could become a columns of the database tables
    # (in the future) to avoid repetitive calculation of constant variables.
    # Nonetheless making decision about each of these should take into account,
    # how often columns and other models referenced in property will be updated
    # (so we can avoid unnecessary whole database rebuilding).

    # We can also use SQL Materialized View
    # For MySQL manual implementation is needed but it is quite straightforward

    @hybrid_property
    def is_ptm(self):
        """Mutation is PTM related if it may affect PTM site.

        Mutations flanking PTM site in a distance up to 7 residues from
        a site (called here 'distal') will be included too.
        """
        return self.is_ptm_distal

    @hybrid_property
    def is_ptm_direct(self):
        """True if the mutation is on the same position as some PTM site."""
        return self.is_close_to_some_site(0, 0)

    @hybrid_property
    def is_ptm_proximal(self):
        """Check if the mutation is in close proximity of some PTM site.

        Proximity is defined here as [pos - 3, pos + 3] span,
        where pos is the position of a PTM site.
        """
        return self.is_close_to_some_site(3, 3)

    @hybrid_property
    def is_ptm_distal(self):
        """Check if the mutation is distal flanking mutation of some PTM site.

        Distal flank is defined here as [pos - 7, pos + 7] span,
        where pos is the position of a PTM site.
        """
        return self.is_close_to_some_site(7, 7)

    @hybrid_property
    def cnt_ptm_affected(self):
        """How many PTM sites might be affected by this mutation,

        when taking into account -7 to +7 spans of each PTM site.
        """
        sites = Protein.query.get(self.protein_id).sites
        pos = self.position
        a = 0
        b = len(sites)

        cnt_affected = 0
        hit = None

        while a != b:
            p = (b - a) // 2 + a
            site_pos = sites[p].position
            if site_pos - 7 <= pos and pos <= site_pos + 7:
                hit = p
                cnt_affected += 1
                break
            if pos > site_pos:
                a = p + 1
            else:
                b = p
        else:
            return 0

        def cond():
            try:
                site_pos = sites[p].position
                return site_pos - 7 <= pos and pos <= site_pos + 7
            except IndexError:
                return False

        # go to right from found site, check if there is more overlappig sites
        p = hit + 1
        while cond():
            cnt_affected += 1
            p += 1

        # and then go to the left
        p = hit - 1
        while cond():
            cnt_affected += 1
            p -= 1

        return cnt_affected

    @cnt_ptm_affected.expression
    def cnt_ptm_affected(self):
        """SQL expression for cnt_ptm_affected"""
        pos = self.position
        count = db.session.query(func.count(Site.id)).\
            filter_by(protein_id=self.protein_id).\
            filter(Site.position.between(pos - 8, pos + 8)).scalar()

        return count

    @hybrid_property
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

    @hybrid_method
    def is_close_to_some_site(self, left, right):
        """Check if the mutation lies close to any of sites.

        Arguments define span around each site to be checked:
        (site_pos - left, site_pos + right)
        site_pos is the position of a site

        Algoritm is based on bisection and an assumption,
        that sites are sorted by position in the database.
        """
        sites = Protein.query.get(self.protein_id).sites
        pos = self.position
        a = 0
        b = len(sites)
        while a != b:
            p = (b - a) // 2 + a
            site_pos = sites[p].position
            if site_pos - left <= pos and pos <= site_pos + right:
                return True
            if pos > site_pos:
                a = p + 1
            else:
                b = p
        return False

    @is_close_to_some_site.expression
    def is_close_to_some_site(self, left, right):
        """SQL expression for is_close_to_some_site"""
        position = self.position
        q = exists().where(
            and_(
                Site.protein_id == self.protein_id,
                Site.position.between(position - left, position + right)
                )
        )
        return db.session.query(q).scalar()
