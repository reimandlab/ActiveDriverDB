from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.declarative.base import declared_attr
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import backref
from werkzeug.utils import cached_property

from database import db, count_expression
from database.types import ScalarSet
from .model import BioModel, make_association_table
from .protein import Protein
from .sites import SiteType


class GeneListEntry(BioModel):
    gene_list_id = db.Column(db.Integer, db.ForeignKey('genelist.id'))

    p = db.Column(db.Float(precision=53))
    fdr = db.Column(db.Float(precision=53))

    gene_id = db.Column(db.Integer, db.ForeignKey('gene.id'))
    gene = db.relationship('Gene')


class ListModel:
    name = db.Column(db.String(255), nullable=False, unique=True, index=True)

    # some lists are specific only to one type of mutations:
    mutation_source_name = db.Column(db.String(256))

    # and/or to only one type of PTM site
    @declared_attr
    def site_type_id(self):
        return db.Column(db.Integer, db.ForeignKey('sitetype.id'))

    @declared_attr
    def site_type(self):
        return db.relationship(SiteType)


class GeneList(ListModel, BioModel):
    entries = db.relationship(GeneListEntry)


class PathwaysListEntry(BioModel):
    pathways_list_id = db.Column(db.Integer, db.ForeignKey('pathwayslist.id'))

    # adjusted.p.val
    fdr = db.Column(db.Float(precision=53))

    pathway_id = db.Column(db.Integer, db.ForeignKey('pathway.id'))
    pathway = db.relationship('Pathway')

    # the overlap as reported by ActivePathways
    overlap = db.Column(ScalarSet(), default=set)

    # pathway size at the time of the computation of the ActivePathways (term.size)
    # just so we can check it in an unlikely case of the the pathways going out of
    # sync with the ActivePathways results
    pathway_size = db.Column(db.Integer)


class PathwaysList(ListModel, BioModel):
    entries = db.relationship(PathwaysListEntry)


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
        return f'<Gene {self.name}, with {len(self.isoforms)} isoforms>'

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

    association_table = make_association_table('pathway.id', Gene.id)

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

    target_genes_association_table = make_association_table('drug.id', Gene.id)

    target_genes = db.relationship(
        Gene,
        secondary=target_genes_association_table,
        backref=db.backref('drugs', cascade='all,delete', passive_deletes=True),
        cascade='all,delete',
        passive_deletes=True
    )

    type_id = db.Column(db.Integer, db.ForeignKey('drugtype.id'))
    type = db.relationship(DrugType, backref='drugs', lazy=False)

    group_association_table = make_association_table('drug.id', DrugGroup.id)

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
