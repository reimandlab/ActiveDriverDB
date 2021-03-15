from typing import List, TYPE_CHECKING

from sqlalchemy import select, case, exists, and_, func, distinct
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property
from werkzeug.utils import cached_property

from database import db, client_side_defaults, fast_count

from .diseases import Cancer, Disease, ClinicalData
from .model import BioModel, make_association_table
from .mutations import Mutation, InheritedMutation
from .sites import Site

if TYPE_CHECKING:
    from .gene import Gene
    from .enzymes import Kinase


class EnsemblPeptide(BioModel):
    reference_id = db.Column(
        db.Integer,
        db.ForeignKey('proteinreferences.id')
    )
    peptide_id = db.Column(db.String(32))


class UniprotEntry(BioModel):
    reference_id = db.Column(
        db.Integer,
        db.ForeignKey('proteinreferences.id')
    )

    # "UniProtKB accession numbers consist of 6 or 10 alphanumerical characters"
    # http://www.uniprot.org/help/accession_numbers
    accession = db.Column(db.String(10))
    isoform = db.Column(db.Integer, nullable=True)
    reviewed = db.Column(db.Boolean, default=False)


class ProteinReferences(BioModel):
    protein_id = db.Column(db.Integer, db.ForeignKey('protein.id'))
    refseq_nm = association_proxy('protein', 'refseq')

    # refseq peptide
    refseq_np = db.Column(db.String(32))

    # refseq gene
    refseq_ng = db.Column(db.String(32))

    # ensembl peptides
    ensembl_peptides = db.relationship('EnsemblPeptide', backref='reference')

    uniprot_association_table = make_association_table(
        'proteinreferences.id',
        UniprotEntry.id
    )

    uniprot_entries = db.relationship(
        UniprotEntry,
        secondary=uniprot_association_table,
        backref='references'
    )


class Protein(BioModel):
    """Protein represents a single isoform of a product of given gene."""

    gene_id = db.Column(db.Integer, db.ForeignKey('gene.id', use_alter=True))
    gene_name = association_proxy('gene', 'name')
    gene: 'Gene'

    external_references = db.relationship(
        'ProteinReferences',
        backref='protein',
        uselist=False
    )

    @property
    def is_swissprot_canonical_isoform(self):
        if self.external_references:
            for entry in self.external_references.uniprot_entries:
                if entry.reviewed and entry.isoform == 1:
                    return True
        return False

    @property
    def best_uniprot_entry(self) -> UniprotEntry:
        if self.external_references:
            entries = self.external_references.uniprot_entries
            if not entries:
                return None
            # try to get canonical swissprot isoform
            for entry in entries:
                if entry.reviewed and entry.isoform == 1:
                    return entry
            # if no canonical one, try to get any swissprot isoform
            for entry in entries:
                if entry.reviewed:
                    return entry
            # if no swissprot, return any isoform
            return entries[0]
        return None

    @property
    def is_swissprot_isoform(self):
        if self.external_references:
            for entry in self.external_references.uniprot_entries:
                if entry.reviewed:
                    return True
        return False

    # refseq id of mRNA sequence (always starts with 'NM_')
    # HGNC reserves up to 50 characters; 32 seems good enough but
    # I did not found any technical documentation; useful resource:
    # ncbi.nlm.nih.gov/books/NBK21091/
    refseq = db.Column(db.String(32), unique=True, index=True)

    # such as 'cellular tumor antigen p53 isoform a' on https://www.ncbi.nlm.nih.gov/protein/NP_000537
    # note: this is different than full >gene< name
    full_name = db.Column(db.Text)

    # summary from Entrez/RefSeq database as at: https://www.ncbi.nlm.nih.gov/gene/7157
    summary = db.Column(db.Text)

    # sequence of amino acids represented by one-letter IUPAC symbols
    sequence = db.Column(db.Text, default='')

    # sequence of ones and zeros where ones indicate disorder region
    # should be no longer than the sequence (defined above)
    disorder_map = db.Column(db.Text, default='')

    # conservation scores as defined by PhyloP - a semicolon separated list
    conservation = db.Column(db.Text, default='')

    # transcription start/end coordinates
    tx_start = db.Column(db.Integer)
    tx_end = db.Column(db.Integer)

    # interactors count will be displayed in NetworkView
    interactors_count = db.Column(db.Integer)

    # coding sequence domain start/end coordinates
    cds_start = db.Column(db.Integer)
    cds_end = db.Column(db.Integer)

    sites: List['Site'] = db.relationship(
        'Site',
        order_by='Site.position',
        backref='protein',
        lazy='immediate'
    )
    mutations: List['Mutation'] = db.relationship(
        'Mutation',
        order_by='Mutation.position',
        lazy='dynamic',
        backref='protein'
    )
    domains: List['Domain'] = db.relationship(
        'Domain',
        backref='protein'
    )
    kinase: List['Kinase'] = db.relationship(
        'Kinase',
        backref='protein'
    )

    @client_side_defaults('sequence', 'disorder_map')
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return f'<Protein {self.refseq} with seq of {self.length} aa from {self.gene.name if self.gene else "-"} gene>'

    @hybrid_property
    def has_ptm_mutations(self):
        # TODO
        raise NotImplementedError

    @has_ptm_mutations.expression
    def has_ptm_mutations(cls):
        return cls.has_ptm_mutations_in_dataset()

    @classmethod
    def has_ptm_mutations_in_dataset(cls, dataset=None):
        criteria = [
            Site.protein_id == cls.id,
            Mutation.protein_id == cls.id,
            Mutation.is_confirmed == True,
            Site.position.between(
                Mutation.position - 7,
                Mutation.position + 7
            )
        ]
        if dataset:
            criteria.append(Mutation.in_sources(dataset))
        return (
            select([
                case(
                    [(
                        exists()
                        .where(and_(*criteria)).correlate(cls),
                        True
                    )],
                    else_=False,
                ).label('has_ptm_mutations')
            ])
            .label('has_ptm_mutations_select')
        )

    @hybrid_property
    def ptm_mutations_count(self):
        return sum(1 for mut in self.confirmed_mutations if mut.precomputed_is_ptm)

    @ptm_mutations_count.expression
    def ptm_mutations_count(cls):
        return (
            select(func.count(Mutation.id))
            .filter(and_(
                Mutation.protein_id == Protein.id,
                Mutation.precomputed_is_ptm,
                Mutation.is_confirmed == True
            ))
        )

    @hybrid_property
    def mutations_count(self):
        return self.mutations.count()

    @mutations_count.expression
    def mutations_count(cls):
        return (
            select([func.count(Mutation.id)]).
            where(Mutation.protein_id == cls.id).
            label('mutations_count')
        )

    @hybrid_property
    def sites_count(self):
        return len(self.sites)

    @sites_count.expression
    def sites_count(cls):
        return (
            select([func.count(Site.id)]).
            where(Site.protein_id == cls.id).
            label('sites_count')
        )

    @hybrid_property
    def confirmed_mutations(self):
        return Mutation.query.filter_by(
            protein=self, is_confirmed=True
        )

    @hybrid_property
    def confirmed_mutations_count(self):
        return fast_count(self.confirmed_mutations)

    def to_json(self, data_filter=None):
        if not data_filter:
            data_filter = list

        filtered_mutations = data_filter(self.confirmed_mutations)

        return {
            'is_preferred': self.is_preferred_isoform,
            'gene_name': self.gene_name,
            'refseq': self.refseq,
            'sites_count': len(data_filter(self.sites)),
            'muts_count': len(filtered_mutations),
            'ptm_muts': sum(
                1 for m in filtered_mutations
                if m.is_ptm()
            )
        }

    @hybrid_property
    def is_preferred_isoform(self):
        return self.gene.preferred_isoform == self

    @is_preferred_isoform.expression
    def is_preferred_isoform(self):
        from .gene import Gene
        return (
            select([
                case(
                    [(
                        exists()
                        .where(and_(
                            Gene.preferred_isoform_id == self.id,
                            Gene.id == self.gene_id
                        )).correlate(self),
                        True
                    )],
                    else_=False,
                ).label('is_preferred_isoform')
            ])
            .label('is_preferred_isoform_select')
        )

    @cached_property
    def length(self):
        """Length of protein's sequence, without the trailing stop (*) character"""
        return len(self.sequence.rstrip('*'))

    @cached_property
    def disorder_length(self):
        """How many residues are disordered."""
        return self.disorder_map.count('1')

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
            kinases.update(site.kinases)
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
            kinase_groups.update(site.kinase_groups)
        return kinase_groups

    @cached_property
    def sites_affecting_positions(self):
        return set(
            i
            for position, in db.session.query(Site.position).filter_by(protein=self)
            for i in range(position - 7, position + 7 + 1)
        )

    def would_affect_any_sites(self, mutation_pos):
        return mutation_pos in self.sites_affecting_positions

    def has_sites_in_range(self, left, right):
        """Test if there are any sites in given range defined as <left, right>, inclusive.

        Algorithm is based on bisection and an assumption,
        that sites are sorted by position in the database.
        """
        assert left < right

        sites = self.sites

        for i, site in enumerate(sites):
            if site.position >= left:
                start = i
                break
        else:
            return False

        for i, site in enumerate(reversed(sites)):
            if site.position <= right:
                return start <= len(sites) - i - 1
        return False

    @property
    def disease_names_by_id(self):
        query = (
            db.session.query(Disease.id, Disease.name)
            .join(ClinicalData)
            .join(InheritedMutation)
            .join(Mutation)
            .filter(Mutation.protein == self)
        )
        return {row[0]: row[1] for row in query}

    def cancer_codes(self, mutation_details_model):
        query = (
            db.session.query(distinct(Cancer.code))
            .join(mutation_details_model)
            .join(Mutation)
            .filter(Mutation.protein == self)
            .order_by(Cancer.name)
        )
        return [row[0] for row in query]

    def _calc_interactors_count(self):
        return len(self.kinases) + len(self.kinase_groups)


class InterproDomain(BioModel):
    # Interpro ID
    accession = db.Column(db.String(64), unique=True)

    # Interpro Short Description
    short_description = db.Column(db.Text)

    # Interpro Description
    description = db.Column(db.Text)

    # is this a family? or domain? or maybe something else?
    type = db.Column(db.String(16))

    # How deep in the hierarchy this interpro domain is placed
    level = db.Column(db.Integer)

    # What is the interpro domain above in hierarchy tree
    parent_id = db.Column(db.Integer, db.ForeignKey('interprodomain.id'))
    parent: 'InterproDomain'

    # Relation with backref allowing easy tree traversal
    children = db.relationship(
        'InterproDomain',
        backref=db.backref('parent', remote_side='InterproDomain.id')
    )

    # Occurrences (annotations) of real biological domains
    occurrences = db.relationship('Domain', backref='interpro')

    def __repr__(self):
        return '<InterproDomain {0} of type {1} on {2} level "{3}" {4}>'.format(
            self.accession,
            self.type,
            self.level,
            self.short_description,
            'with parent: ' + str(self.parent.accession)
            if self.parent_id
            else ''
        )


class Domain(BioModel):
    protein_id = db.Column(db.Integer, db.ForeignKey('protein.id'))
    interpro_id = db.Column(db.Integer, db.ForeignKey('interprodomain.id'))
    interpro: InterproDomain

    start = db.Column(db.Integer)
    end = db.Column(db.Integer)

    def __len__(self):
        return self.end - self.start

    def __repr__(self):
        return '<Domain "{0}" in {1}, at [{2}, {3}] >'.format(
            self.interpro.accession,
            self.protein.refseq,
            self.start,
            self.end
        )
