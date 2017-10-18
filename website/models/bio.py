from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from collections import UserList

from sqlalchemy import and_, distinct
from sqlalchemy import case
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.hybrid import hybrid_method, Comparator
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import backref, synonym
from sqlalchemy.sql import exists
from sqlalchemy.sql import select
from werkzeug.utils import cached_property

from database import db, count_expression
from database import fast_count
from exceptions import ValidationError
from helpers.models import generic_aggregator, association_table_super_factory
from models import Model


class BioModel(Model):
    """Models descending from BioData are supposed to hold biology-related data

    and will be stored in a 'bio' database, separated from visualization
    settings and other data handled by 'content management system'.
    """
    __abstract__ = True
    __bind_key__ = 'bio'


make_association_table = association_table_super_factory(bind='bio')


class GeneListEntry(BioModel):
    gene_list_id = db.Column(db.Integer, db.ForeignKey('genelist.id'))

    p = db.Column(db.Float(precision=53))
    fdr = db.Column(db.Float(precision=53))

    gene_id = db.Column(db.Integer, db.ForeignKey('gene.id'))
    gene = db.relationship('Gene')


class GeneList(BioModel):
    name = db.Column(db.String(256), nullable=False, unique=True, index=True)
    entries = db.relationship(GeneListEntry)

    # some gene lists are specific only to one type of mutations:
    mutation_source_name = db.Column(db.String(256))


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

    def __repr__(self):
        return '<Kinase {0} belonging to {1} group>'.format(
            self.name,
            self.group
        )

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

    def __repr__(self):
        return '<KinaseGroup {0}, with {1} kinases>'.format(
            self.name,
            len(self.kinases)
        )


class Gene(BioModel):
    """Gene is uniquely identified although has multiple protein isoforms.

    The isoforms are always located on the same chromosome, strand and are
    a product of the same gene. The major function of this model is to group
    isoforms classified as belonging to the same gene and to verify
    consistency of chromosomes and strands information across the database.
    """
    # HGNC symbols are allowed to be varchar(255) but 40 is still safe
    # as for storing symbols that are currently in use. Let's use 2 x 40.
    name = db.Column(db.String(80), unique=True, index=True)

    # Full name from HGNC
    full_name = db.Column(db.Text)

    # TRUE represent positive (+) strand, FALSE represents negative (-) strand
    # As equivalent to (?) from Generic Feature Format NULL could be used.
    strand = db.Column(db.Boolean())

    # Chromosome - up to two digits (1-22 inclusive), X and Y and eventually MT
    chrom = db.Column(db.CHAR(2))

    # "Records in Entrez Gene are assigned unique, stable and tracked integers as identifiers"
    # ncbi.nlm.nih.gov/pmc/articles/PMC3013746, doi: 10.1093/nar/gkq1237
    # as for Jun 8 2017, there are 18 151 636 genes in Entrez (ncbi.nlm.nih.gov/gene/statistics)
    # an integer should suffice up to 2,147,483,647 genes.
    entrez_id = db.Column(db.Integer)

    isoforms = db.relationship(
        'Protein',
        backref=backref('gene', lazy='immediate'),
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
    preferred_refseq = association_proxy('preferred_isoform', 'refseq')

    @cached_property
    def alternative_isoforms(self):
        return [
            isoform
            for isoform in self.isoforms
            if isoform.id != self.preferred_isoform_id
        ]

    @hybrid_property
    def isoforms_count(self):
        return len(self.isoforms)

    @isoforms_count.expression
    def isoforms_count(cls):
        return count_expression(cls, Protein)

    @hybrid_property
    def is_known_kinase(self):
        return bool(self.preferred_isoform.kinase)

    def __repr__(self):
        return '<Gene {0}, with {1} isoforms>'.format(
            self.name,
            len(self.isoforms)
        )

    def to_json(self):
        return {
            'name': self.name,
            'preferred_isoform': (
                self.preferred_refseq
                if self.preferred_isoform
                else None
            ),
            'isoforms_count': self.isoforms_count
        }


class Pathway(BioModel):
    description = db.Column(db.Text)

    gene_ontology = db.Column(db.Integer)
    reactome = db.Column(db.Integer)

    association_table = make_association_table('pathway.id', 'gene.id')

    genes = db.relationship(
        'Gene',
        secondary=association_table,
        backref='pathways'
    )

    @hybrid_property
    def gene_count(self):
        return len(self.genes)

    @gene_count.expression
    def gene_count(cls):
        return count_expression(cls, Gene, Gene.pathways)

    def to_json(self):
        return {
            'id': self.id,
            'description': self.description,
            'reactome': self.reactome,
            'gene_ontology': self.gene_ontology,
            'gene_count': self.gene_count,
            'genes': [
                {
                    'name': gene,
                    'preferred_isoform': {'refseq': refseq} if refseq else None
                }
                for gene, refseq in (
                    db.session.query(Gene.name, Protein.refseq)
                        .select_from(Pathway)
                        .filter(Pathway.id == self.id)
                        .join(Pathway.association_table)
                        .join(Gene)
                        .outerjoin(Protein, Gene.preferred_isoform_id == Protein.id)
                )
            ]
        }


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
    isoform = db.Column(db.Integer)
    reviewed = db.Column(db.Boolean, default=False)


class ProteinReferences(BioModel):
    protein_id = db.Column(db.Integer, db.ForeignKey('protein.id'))
    refseq_nm = association_proxy('protein', 'refseq')

    # refseq peptide
    refseq_np = db.Column(db.String(32))

    # refseq gene
    refseq_ng = db.Column(db.String(32))

    # ensembl peptides
    ensembl_peptides = db.relationship('EnsemblPeptide',  backref='reference')

    uniprot_entries = db.relationship(UniprotEntry, backref='reference')


class DrugGroup(BioModel):
    """>Drugs are categorized by group, which determines their drug development status.<
    A drug can belong to multiple groups.

    Relevant schema definition fragment (drugbank.xsd):

    <xs:complexType name="group-list-type">
        <xs:sequence maxOccurs="6" minOccurs="1">
            <xs:element name="group" type="group-type"/>
        </xs:sequence>
    </xs:complexType>
    <xs:simpleType name="group-type">
        <xs:annotation>
            <xs:documentation>Drugs are grouped into a category like approved, experimental, illict.</xs:documentation>
        </xs:annotation>
        <xs:restriction base="xs:string">
            <xs:enumeration value="approved"/>
            <xs:enumeration value="illicit"/>
            <xs:enumeration value="experimental"/>
            <xs:enumeration value="withdrawn"/>
            <xs:enumeration value="nutraceutical"/>
            <xs:enumeration value="investigational"/>
            <xs:enumeration value="vet_approved"/>
        </xs:restriction>
    </xs:simpleType>

    """
    name = db.Column(db.String(32), unique=True, index=True)


class DrugType(BioModel):
    """Drug type is either 'small molecule' or 'biotech'.
    Every drug has only one type.

    Relevant schema definition fragment (drugbank.xsd):

    <xs:attribute name="type" use="required">
        <xs:simpleType>
            <xs:restriction base="xs:string">
                <xs:enumeration value="small molecule"/>
                <xs:enumeration value="biotech"/>
            </xs:restriction>
        </xs:simpleType>
    </xs:attribute>
    """
    name = db.Column(db.String(32), unique=True, index=True)


class Drug(BioModel):
    name = db.Column(db.String(128))
    drug_bank_id = db.Column(db.String(32))
    description = db.Column(db.Text)

    target_genes_association_table = make_association_table('drug.id', 'gene.id')

    target_genes = db.relationship(
        Gene,
        secondary=target_genes_association_table,
        backref=db.backref('drugs', cascade='all,delete', passive_deletes=True),
        cascade='all,delete',
        passive_deletes=True
    )

    type_id = db.Column(db.Integer, db.ForeignKey('drugtype.id'))
    type = db.relationship(DrugType, backref='drugs', lazy=False)

    group_association_table = make_association_table('drug.id', 'druggroup.id')

    groups = db.relationship(
        DrugGroup,
        secondary=group_association_table,
        collection_class=set,
        backref='drugs'
    )

    def to_json(self):
        return {
            'name': self.name,
            'type': self.type.name if self.type else '',
            'groups': [drug_group.name for drug_group in self.groups],
            'drugbank': self.drug_bank_id
        }


class Protein(BioModel):
    """Protein represents a single isoform of a product of given gene."""

    gene_id = db.Column(db.Integer, db.ForeignKey('gene.id', use_alter=True))
    gene_name = association_proxy('gene', 'name')

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

    # transcription start/end coordinates
    tx_start = db.Column(db.Integer)
    tx_end = db.Column(db.Integer)

    # interactors count will be displayed in NetworkView
    interactors_count = db.Column(db.Integer)

    # coding sequence domain start/end coordinates
    cds_start = db.Column(db.Integer)
    cds_end = db.Column(db.Integer)

    sites = db.relationship(
        'Site',
        order_by='Site.position',
        backref='protein',
        lazy='immediate'
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
            self.gene.name if self.gene else '-'
        )

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
            from stats import Statistics
            criteria.append(
                Statistics.get_filter_by_sources([dataset])
            )
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
            data_filter = lambda x: list(x)

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
    def disease_names(self):
        query = (
            db.session.query(distinct(Disease.name))
            .join(ClinicalData)
            .join(InheritedMutation)
            .join(Mutation)
            .filter(Mutation.protein == self)
        )
        return [row[0] for row in query]

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


def default_residue(context):
    params = context.current_parameters

    protein = params.get('protein')
    protein_id = params.get('protein_id')

    if not protein and protein_id:
        protein = Protein.query.get(protein_id)

    position = params.get('position')

    if protein and position:
        try:
            return protein.sequence[position]
        except IndexError:
            print('Position of PTM possibly exceeds its protein')
            return


class Site(BioModel):
    # Note: this position is 1-based
    position = db.Column(db.Integer, index=True)

    residue = db.Column(db.String(1), default=default_residue)
    pmid = db.Column(db.Text)
    # type is expected to be a spaceless string, one of following:
    #   phosphorylation acetylation ubiquitination methylation
    # or comma separated list consisting of such strings. Another
    # implementation which should be tested would use relationships
    # to 'site_types' table and it might be faster to query specific
    # sites when having this implemented that way.
    type = db.Column(db.Text)
    protein_id = db.Column(db.Integer, db.ForeignKey('protein.id'))
    kinases = db.relationship(
        'Kinase',
        secondary=make_association_table('site.id', 'kinase.id'),
        backref='sites'
    )
    kinase_groups = db.relationship(
        'KinaseGroup',
        secondary=make_association_table('site.id', 'kinasegroup.id'),
        backref='sites'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.validate_position()
        self.validate_residue()

    def get_nearby_sequence(self, protein, dst=3):
        left = self.position - dst - 1
        right = self.position + dst
        return (
            '-' * -min(0, left) +
            protein.sequence[max(0, left):min(right, protein.length)] +
            '-' * max(0, right - protein.length)
        )

    @hybrid_property
    def sequence(self):
        return self.get_nearby_sequence(self.protein, dst=7)

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

    def validate_position(self):
        position = self.position
        if self.protein:
            if position > self.protein.length or position < 0:
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
            'type': self.type,
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

    types = [
        'phosphorylation', 'acetylation',
        'ubiquitination', 'methylation'
    ]


class Cancer(BioModel):
    code = db.Column(db.String(16), unique=True)
    name = db.Column(db.String(64), unique=True)

    def __repr__(self):
        return '<Cancer with code: {0}, named: {1}>'.format(
            self.code,
            self.name
        )


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


mutation_site_association = make_association_table('site.id', 'mutation.id')


class MutationDetailsManager(UserList, metaclass=ABCMeta):
    """Groups (by a unique mutation) mutation details from a given source"""

    @property
    @abstractmethod
    def name(self):
        """Internal name which has to remain unchanged, used in relationships"""
        pass

    @property
    @abstractmethod
    def value_type(self):
        """What is the value returned by 'get_value'.

        It can be 'count', 'frequency' or 'probability'.
        """
        pass

    @abstractmethod
    def to_json(self):
        pass

    def get_value(self, filter=lambda x: x):
        return sum(
            (
                data.get_value()
                for data in filter(self.data)
            )
        )

    summary = generic_aggregator('summary', is_callable=True)


def create_cancer_meta_manager(meta_name):

    class CancerMetaManager(MutationDetailsManager):
        name = meta_name
        value_type = 'count'

        def to_json(self, filter=lambda x: x):
            cancer_occurrences = [
                datum.to_json()
                for datum in
                filter(self.data)
            ]

            return {meta_name + 'metadata': cancer_occurrences}

        def summary(self, filter=lambda x: x):
            return [
                datum.summary()
                for datum in self.data
                # one could use:

                # for datum in filter(self.data)

                # so only the cancer data from currently selected cancer type are show,
                # but then the user may think that the mutation is specific for this
                # type of cancer
            ]

    return CancerMetaManager


class MIMPMetaManager(MutationDetailsManager):

    name = 'MIMP'
    value_type = 'probability'

    @staticmethod
    def sort_by_probability(mimps):
        return mimps.sort(
            key=lambda mimp: mimp.probability,
            reverse=True
        )

    def to_json(self, filter=lambda x: x):

        gains = []
        losses = []

        for mimp in self.data:
            if mimp.is_gain:
                gains.append(mimp)
            else:
                losses.append(mimp)

        self.sort_by_probability(gains)
        self.sort_by_probability(losses)

        return {
            'gain': [mimp.to_json() for mimp in gains],
            'loss': [mimp.to_json() for mimp in losses],
            'effect': self.effect
        }

    @property
    def effect(self):
        effects = set()

        # TODO: sort by p-value, so first we will have loss
        # if the loss data is more reliable and vice versa.
        for mimp in self.data:
            if mimp.is_gain:
                effects.add('gain')
            else:
                effects.add('loss')

        return '/'.join(effects)

    @property
    def sites(self):
        return set(
            (
                mimp.site
                for mimp in self.data
            )
        )


class MutationDetails:
    """Base for tables defining detailed metadata for specific mutations"""

    @declared_attr
    def mutation_id(cls):
        return db.Column(db.Integer, db.ForeignKey('mutation.id'), unique=True)

    def get_value(self, filter=lambda x: x):
        """Return number representing value to be used in needleplot"""
        raise NotImplementedError

    def to_json(self, filter=lambda x: x):
        """Return JSON serializable representation for needleplot tooltips.

        The default serializer is: json.JSONEncoder
            https://docs.python.org/3/library/json.html#json.JSONEncoder
        """
        raise NotImplementedError

    def summary(self, filter=lambda x: x):
        """Return short JSON serializable representation of the mutation"""
        raise NotImplementedError

    @property
    def display_name(self):
        """Name which will be shown to the user (e.g. in filters panel)"""
        raise NotImplementedError

    @property
    def name(self):
        """Internal name which has to remain unchanged, used in relationships"""
        raise NotImplementedError

    @property
    def value_type(self):
        """What is the value returned by 'get_value'.

        Either 'count' or 'frequency'.
        """
        raise NotImplementedError

    def __repr__(self):
        return '<{class_name} - details of {refseq}:{mutation} with summary: {summary}>'.format(
            class_name=self.name,
            refseq=self.mutation.protein.refseq,
            mutation=self.mutation.short_name,
            summary=self.summary()
        )


class ManagedMutationDetails(MutationDetails):
    """For use when one mutation is related to many mutation details entries."""

    @property
    def details_manager(self):
        """Collection class (deriving from MutationDetailsManager) which will
        aggregate results from all the mutation details (per mutation).
        """
        raise NotImplementedError

    @declared_attr
    def mutation_id(cls):
        return db.Column(db.Integer, db.ForeignKey('mutation.id'))


class UserUploadedMutation(MutationDetails, BioModel):

    name = 'user'
    display_name = 'User\'s mutations'

    value_type = 'count'

    count = db.Column(db.Integer, default=0)
    query = db.Column(db.Text)

    def get_value(self, filter=lambda x: x):
        return self.count

    def to_json(self, filter=lambda x: x):
        return {
            'Query': self.query,
            'Value': self.count
        }

    def summary(self, filter=lambda x: x):
        return self.query


class CancerMutation(ManagedMutationDetails):

    samples = db.Column(db.Text(), default='')
    value_type = 'count'
    count = db.Column(db.Integer)

    @declared_attr
    def cancer_id(self):
        return db.Column(db.Integer, db.ForeignKey('cancer.id'))

    @declared_attr
    def cancer(self):
        return db.relationship('Cancer')

    def get_value(self, filter=lambda x: x):
        return self.count

    def to_json(self, filter=None):
        return {
            'Cancer': self.cancer.name,
            'Value': self.count
        }

    def summary(self, filter=lambda x: x):
        return self.cancer_code


class MC3Mutation(CancerMutation, BioModel):
    """Metadata for cancer mutations from ICGC data portal"""
    name = 'MC3'
    display_name = 'Cancer (TCGA PanCancerAtlas)'
    details_manager = create_cancer_meta_manager('MC3')
    mc3_cancer_code = association_proxy('cancer', 'code')
    cancer_code = mc3_cancer_code


class TCGAMutation(CancerMutation, BioModel):
    name = 'TCGA'
    display_name = 'Cancer (TCGA Pancan12)'
    details_manager = create_cancer_meta_manager('TCGA')
    tcga_cancer_code = association_proxy('cancer', 'code')
    cancer_code = tcga_cancer_code


class InheritedMutation(MutationDetails, BioModel):
    """Metadata for inherited diseased mutations from ClinVar from NCBI

    Columns description come from source VCF file headers.
    """
    name = 'ClinVar'
    display_name = 'Clinical (ClinVar)'
    value_type = 'count'

    # RS: dbSNP ID (i.e. rs number)
    db_snp_ids = db.Column(db.PickleType)

    # MUT: Is mutation (journal citation, explicit fact):
    # a low frequency variation that is cited
    # in journal and other reputable sources
    is_low_freq_variation = db.Column(db.Boolean)

    # VLD: This bit is set if the variant has 2+ minor allele
    # count based on frequency or genotype data
    is_validated = db.Column(db.Boolean)

    # PMC: Links exist to PubMed Central article
    is_in_pubmed_central = db.Column(db.Boolean)

    clin_data = db.relationship('ClinicalData', uselist=True)

    sig_code = association_proxy('clin_data', 'sig_code')
    disease_name = association_proxy('clin_data', 'disease_name')

    def get_value(self, filter=lambda x: x):
        return len(filter(self.clin_data))

    def to_json(self, filter=lambda x: x):
        return {
            'dbSNP id': self.db_snp_ids or [],
            'Is validated': bool(self.is_validated),
            'Is low frequency variation': bool(self.is_low_freq_variation),
            'Is in PubMed Central': bool(self.is_in_pubmed_central),
            'Clinical': [
                d.to_json()
                for d in filter(self.clin_data)
            ]
        }

    def summary(self, filter=lambda x: x):
        return list(set(
            d.disease_name
            for d in filter(self.clin_data)
        ))


class Disease(BioModel):

    __table_args__ = (
      db.Index('idx_name', 'name', mysql_length=1024),
    )

    # CLNDBN: Variant disease name
    name = db.Column(db.Text, nullable=False, unique=True)


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


def population_manager(_name, _display_name):

    class PopulationManager(MutationDetailsManager):
        """Some population mutations annotations are provided in form of a several
        separate records, where all the records relate to the same aminoacid mutation.

        Assuming that the frequencies are summable, one could merge the annotations
        at the time of import. However, the information about the distribution of
        nucleotide mutation frequencies would be lost if merging at import time.

        Aggregation of the mutations details in PopulationManager allows to have both
        overall and nucleotide-mutation specific frequencies included."""
        name = _name
        display_name = _display_name
        value_type = 'frequency'

        affected_populations = property(generic_aggregator('affected_populations', flatten=True))

        def to_json(self, filter=lambda x: x):
            data = filter(self.data)
            json = data[0].to_json()
            for datum in data[1:]:
                for k, v in datum.to_json().items():
                    json[k] = str(json[k]) + ', ' + str(v)
            return json

    return PopulationManager


class PopulationsComparator(Comparator):
    """Given a population name, or list of population names,
    determine if PopulationMutation include this population
    (i.e. has non-zero frequency of occurrence in the population)
    """

    def __init__(self, cls):
        self.populations_fields = cls.populations_fields()
        self.cls = cls

    def __eq__(self, population_name):
        return getattr(self.cls, self.populations_fields[population_name]) > 0

    def in_(self, population_names):

        return or_(
            *[
                getattr(self.cls, self.populations_fields[population_name]) > 0
                for population_name in population_names
            ]
        )


class PopulationMutation(ManagedMutationDetails):
    """Metadata common for mutations from all population-wide studies

    MAF:
        All - total value
    """
    populations = {
        # place mappings here: field name -> population name
    }

    @classmethod
    def populations_fields(cls):
        return {v: k for k, v in cls.populations.items()}

    maf_all = db.Column(db.Float)

    def get_value(self, filter=lambda x: x):
        return self.maf_all

    def summary(self, filter=lambda x: x):
        return self.get_value()

    @hybrid_property
    def affected_populations(self):
        return [
            population_name
            for field, population_name in self.populations.items()
            if getattr(self, field)
        ]

    @affected_populations.comparator
    def affected_populations(cls):
        return PopulationsComparator(cls)


class ExomeSequencingMutation(PopulationMutation, BioModel):
    """Metadata for ESP 6500 mutation

    MAF:
        EA - European American
        AA - African American
    """

    name = 'ESP6500'
    display_name = 'Population (ESP 6500)'
    details_manager = population_manager(name, display_name)

    value_type = 'frequency'

    populations = OrderedDict(
        (
            ('maf_ea', 'European American'),
            ('maf_aa', 'African American')
        )
    )

    maf_ea = db.Column(db.Float)
    maf_aa = db.Column(db.Float)

    populations_ESP6500 = synonym('affected_populations')

    def to_json(self, filter=lambda x: x):
        return {
            'MAF': self.maf_all,
            'MAF EA': self.maf_ea,
            'MAF AA': self.maf_aa,
        }


class The1000GenomesMutation(PopulationMutation, BioModel):
    """Metadata for 1 KG mutation"""
    name = '1KGenomes'
    display_name = 'Population (1000 Genomes)'
    details_manager = population_manager(name, display_name)

    value_type = 'frequency'

    maf_eas = db.Column(db.Float)
    maf_amr = db.Column(db.Float)
    maf_afr = db.Column(db.Float)
    maf_eur = db.Column(db.Float)
    maf_sas = db.Column(db.Float)

    # note: those are defined as super populations by 1000 Genomes project
    populations = OrderedDict(
        (
            ('maf_eas', 'East Asian'),
            ('maf_amr', 'Ad Mixed American'),
            ('maf_afr', 'African'),
            ('maf_eur', 'European'),
            ('maf_sas', 'South Asian')
        )
    )

    def to_json(self, filter=lambda x: x):
        return {
            'MAF': self.maf_all,
            'MAF EAS': self.maf_eas,
            'MAF AMR': self.maf_amr,
            'MAF AFR': self.maf_afr,
            'MAF EUR': self.maf_eur,
            'MAF SAS': self.maf_sas,
        }

    populations_1KG = synonym('affected_populations')


class MIMPMutation(ManagedMutationDetails, BioModel):
    """Metadata for MIMP mutation"""

    name = 'MIMP'
    display_name = 'MIMP'

    details_manager = MIMPMetaManager

    site_id = db.Column(db.Integer, db.ForeignKey('site.id'))
    site = db.relationship('Site')

    probability = db.Column(db.Float)

    pwm = db.Column(db.Text)
    pwm_family = db.Column(db.Text)

    kinase = db.relationship(
        'Kinase',
        primaryjoin='foreign(Kinase.name)==MIMPMutation.pwm',
        uselist=False
    )
    kinase_group = db.relationship(
        'KinaseGroup',
        primaryjoin='foreign(KinaseGroup.name)==MIMPMutation.pwm_family',
        uselist=False
    )

    # gain = +1, loss = -1
    effect = db.Column(db.Boolean)

    effect_map = {
        'gain': 1,
        'loss': 0
    }

    def __init__(self, **kwargs):
        effect = kwargs.get('effect', None)
        if effect in self.effect_map:
            kwargs['effect'] = self.effect_map[effect]
        super().__init__(**kwargs)

    @property
    def is_gain(self):
        return self.effect

    @property
    def is_loss(self):
        return not self.effect

    # position of a mutation in an associated motif
    position_in_motif = db.Column(db.Integer)

    def to_json(self, filter=lambda x: x):
        return {
            'effect': 'gain' if self.is_gain else 'loss',
            'pwm': self.pwm,
            'kinase': {'refseq': self.kinase.protein.refseq} if self.kinase and self.kinase.protein else {},
            'pos_in_motif': self.position_in_motif,
            'pwm_family': self.pwm_family,
            'site': self.site.to_json() if self.site else None,
            'probability': self.probability
        }


def details_proxy(target_class, key, managed=False):
    """Creates an AssociationProxy targeting MutationDetails descendants.
    The proxy enables easy filtering and retrieval of the otherwise deeply
    hidden information and should be owned by (i.e. declared in) Mutation model.

    Attributes:
        managed: if True, a request for server side filtering system
            (as opposite to database side filtering) to use attribute
            of name 'key' from 'MutationDetailsManager' (instead of
            the one from the MutationDetails itself) will be encoded
            in the proxy function.

    """

    field_name = 'meta_' + target_class.name
    proxy = association_proxy(field_name, key)

    if managed:
        def proxy_to_details_manager(object):
            if type(object) is Mutation:
                manager = getattr(object, field_name)
            elif isinstance(object, ManagedMutationDetails):
                manager = object.details_manager
            else:
                assert isinstance(object, MutationDetailsManager)
                manager = object
            return getattr(manager, key)
        proxy.custom_attr_getter = proxy_to_details_manager

    return proxy


def are_details_managed(model):
    return ManagedMutationDetails in model.mro()


def mutation_details_relationship(model, use_list=False, **kwargs):
    return db.relationship(
        model,
        backref='mutation',
        uselist=use_list,
        **kwargs
    )


def managed_mutation_details_relationship(model):
    return mutation_details_relationship(
        model,
        use_list=True,
        collection_class=model.details_manager
    )


class Mutation(BioModel):
    __table_args__ = (
        db.Index('mutation_index', 'alt', 'protein_id', 'position'),
        db.UniqueConstraint('alt', 'protein_id', 'position')
    )

    position = db.Column(db.Integer)
    alt = db.Column(db.String(1))
    protein_id = db.Column(db.Integer, db.ForeignKey('protein.id'))

    # To speed up results retrieval one can precompute value of
    # 'is_ptm' property. It does not carry meaningful information
    # for novel mutations until correctly precomputed (e.g. with
    # instruction: m.precomputed_is_ptm = m.is_ptm).
    # You can distinguish if it was precomputed: check if the value
    # is different than None. Be careful with boolean evaluation!
    precomputed_is_ptm = db.Column(db.Boolean)

    types = ('direct', 'network-rewiring', 'proximal', 'distal', 'none')

    # order matters (widget's labels will show up in this order)
    source_specific_data = [
        # TCGAMutation,
        MC3Mutation,
        InheritedMutation,
        ExomeSequencingMutation,
        The1000GenomesMutation,
        UserUploadedMutation,
        MIMPMutation
    ]

    source_data_relationships = {
        'meta_' + model.name: (
            managed_mutation_details_relationship(model)
            if are_details_managed(model) else
            mutation_details_relationship(model)
        )
        for model in source_specific_data
    }

    vars().update(source_data_relationships)

    @classmethod
    def get_source_model(cls, name):
        for model in cls.source_specific_data:
            if model.name == name:
                return model

    @classmethod
    def get_relationship(cls, mutation_class, class_relation_map={}):
        if not class_relation_map:
            for model in cls.source_specific_data:
                class_relation_map[model] = getattr(cls, 'meta_' + model.name)
        return class_relation_map[mutation_class]

    source_fields = OrderedDict(
        (model.name, 'meta_' + model.name)
        for model in source_specific_data
        if model != MIMPMutation
    )

    populations_1KG = details_proxy(The1000GenomesMutation, 'affected_populations', managed=True)
    populations_ESP6500 = details_proxy(ExomeSequencingMutation, 'affected_populations', managed=True)
    mc3_cancer_code = details_proxy(MC3Mutation, 'mc3_cancer_code')
    sig_code = details_proxy(InheritedMutation, 'sig_code')
    disease_name = details_proxy(InheritedMutation, 'disease_name')

    def __repr__(self):
        return '<Mutation in {0}, at {1} aa, substitution to: {2}>'.format(
            self.protein.refseq if self.protein else '-',
            self.position,
            self.alt
        )

    @hybrid_property
    def sources_dict(self):
        """Return list of names of sources which mention this mutation

        Names of sources are determined by source_fields class property.
        """
        sources = {}
        for source_name, associated_field in self.source_fields.items():
            field_value = getattr(self, associated_field)
            if field_value:
                sources[source_name] = field_value
        return sources

    @hybrid_property
    def sources(self):
        """Return list of names of sources which mention this mutation

        Names of sources are determined by source_fields class property.
        """
        sources = []
        for source_name, associated_field in self.source_fields.items():
            if getattr(self, associated_field):
                sources.append(source_name)
        return sources

    @hybrid_property
    def confirmed_fields(cls):
        return [
            getattr(cls, field_name)
            for field_name in cls.source_fields.values()
            if field_name != 'meta_user'
        ]

    @hybrid_property
    def is_confirmed(self):
        """Mutation is confirmed if there are metadata from one of four studies

        (or experiments). Presence of MIMP metadata does not imply
        if mutation has been ever studied experimentally before.
        """
        return any(self.confirmed_fields)

    @is_confirmed.expression
    def is_confirmed(cls):
        """SQL expression for is_confirmed"""
        return or_(
            relationship_field.any()
            if relationship_field.prop.uselist
            else relationship_field.has()
            for relationship_field in cls.confirmed_fields
        )

    @property
    def sites(self):
        return self.get_affected_ptm_sites()

    @hybrid_method
    def is_ptm(self, filter_manager=None):
        """Mutation is PTM related if it may affect PTM site.

        Mutations flanking PTM site in a distance up to 7 residues
        from a site (called here 'distal') will be included too.

        This method works very similarly to is_ptm_distal property.
        """
        sites = self.protein.sites
        if filter_manager:
            sites = filter_manager.apply(sites)
        return self.is_close_to_some_site(7, 7, sites)

    @hybrid_property
    def ref(self):
        sequence = self.protein.sequence
        return sequence[self.position - 1]

    @hybrid_property
    def is_ptm_direct(self):
        """True if the mutation is on the same position as some PTM site."""
        return self.is_close_to_some_site(0, 0)

    @hybrid_property
    def is_ptm_proximal(self):
        """Check if the mutation is in close proximity of some PTM site.

        Proximity is defined here as [pos - 2, pos + 2] span,
        where pos is the position of a PTM site.
        """
        return self.is_close_to_some_site(2, 2)

    @hybrid_property
    def is_ptm_distal(self):
        """Check if the mutation is distal flanking mutation of some PTM site.

        Distal flank is defined here as [pos - 7, pos + 7] span,
        where pos is the position of a PTM site.
        """
        # if we have precomputed True or False (i.e. it's known
        # mutations - so we precomputed this) then return this
        if self.precomputed_is_ptm is not None:
            return self.precomputed_is_ptm
        # otherwise it's a novel mutation - let's check proximity
        return self.is_close_to_some_site(7, 7)

    def get_affected_ptm_sites(self, site_filter=lambda x: x):
        """Get PTM sites that might be affected by this mutation,

        when taking into account -7 to +7 spans of each PTM site.
        """
        sites = site_filter(self.protein.sites)
        pos = self.position
        a = 0
        b = len(sites)
        sites_affected = set()

        while a != b:
            pivot = (b - a) // 2 + a
            site_pos = sites[pivot].position
            if site_pos - 7 <= pos <= site_pos + 7:
                hit = pivot
                sites_affected.add(sites[pivot])
                break
            if pos > site_pos:
                a = pivot + 1
            else:
                b = pivot
        else:
            return tuple()

        def cond():
            try:
                site_pos = sites[pivot].position
                return site_pos - 7 <= pos <= site_pos + 7
            except IndexError:
                return tuple()

        # go to right from found site, check if there is more overlapping sites
        pivot = hit + 1
        while cond():
            sites_affected.add(sites[pivot])
            pivot += 1

        # and then go to the left
        pivot = hit - 1
        while cond():
            sites_affected.add(sites[pivot])
            pivot -= 1

        return list(sites_affected)

    def impact_on_specific_ptm(self, site, ignore_mimp=False):
        if self.position == site.position:
            return 'direct'
        elif site in self.meta_MIMP.sites and not ignore_mimp:
            return 'network-rewiring'
        elif abs(self.position - site.position) < 3:
            return 'proximal'
        elif abs(self.position - site.position) < 8:
            return 'distal'
        else:
            return 'none'

    def impact_on_ptm(self, site_filter=lambda x: x):
        """How intense might be an impact of the mutation on a PTM site.

        It describes impact on the closest PTM site or on a site chosen by
        MIMP algorithm (so it applies only when 'network-rewiring' is returned)
        """
        sites = site_filter(self.protein.sites)

        if self.is_close_to_some_site(0, 0, sites):
            return 'direct'
        elif any(site in sites for site in self.meta_MIMP.sites):
            return 'network-rewiring'
        elif self.is_close_to_some_site(2, 2, sites):
            return 'proximal'
        elif self.is_close_to_some_site(7, 7, sites):
            return 'distal'
        return 'none'

    def find_closest_sites(self, distance=7, site_filter=lambda x: x):
        # TODO: implement site type filter
        pos = self.position

        sites = Site.query.filter(
            and_(
                Site.protein_id == self.protein_id,
                Site.position.between(pos - distance, pos + distance)
            )
        ).order_by(func.abs(Site.position - pos)).limit(2).all()

        if(
                        len(sites) == 2 and
                        abs(sites[0].position - pos) != abs(sites[1].position - pos)
        ):
            return sites[:1]
        else:
            return sites

    @hybrid_method
    def is_close_to_some_site(self, left, right, sites=None):
        """Check if the mutation lies close to any of sites.

        Arguments define span around each site to be checked:
        (site_pos - left, site_pos + right)
        site_pos is the position of a site

        Algorithm is based on bisection and an assumption,
        that sites are sorted by position in the database.
        """
        if sites is None:
            sites = self.protein.sites
        pos = self.position
        a = 0
        b = len(sites)
        while a != b:
            p = (b - a) // 2 + a
            site_pos = sites[p].position
            if site_pos - left <= pos <= site_pos + right:
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

    @property
    def short_name(self):
        return '%s%s%s' % (self.ref, self.position, self.alt)

    @property
    def name(self):
        return '%s %s' % (self.protein.gene.name, self.short_name)

    def to_json(self):
        return {
            'name': self.name,
            'is_confirmed': self.is_confirmed,
            'is_ptm': self.is_ptm()
        }
