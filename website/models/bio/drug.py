from typing import List

from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.declarative.base import declared_attr

from database import db
from database.types import ScalarSet
from models import BioModel, make_association_table, Gene


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
    """
    In case of strange collation encoding errors (due to utf characters in names),
    checkout: https://stackoverflow.com/a/1008336/
    """

    name = db.Column(db.String(128))
    drug_bank_id = db.Column(db.String(32))
    description = db.Column(db.Text)

    type_id = db.Column(db.Integer, db.ForeignKey(DrugType.id))
    type = db.relationship(DrugType, backref='drugs', lazy=False)

    group_association_table = make_association_table('drug.id', DrugGroup.id)

    groups = db.relationship(
        DrugGroup,
        secondary=group_association_table,
        collection_class=set,
        backref='drugs'
    )

    targets: List['DrugTarget']
    target_genes: List[Gene] = association_proxy('targets', 'gene')

    def to_json(self):
        return {
            'name': self.name,
            'type': self.type.name if self.type else '',
            'groups': [drug_group.name for drug_group in self.groups],
            'drugbank': self.drug_bank_id
        }


class DrugTarget(BioModel):
    """Gene/protein target of a drug.

    Relevant schema definition fragments (drugbank.xsd):

    <xs:complexType name="target-type">
        <xs:sequence>
            <xs:group ref="interactant-group"/>
        </xs:sequence>
        <xs:attribute name="position" type="xs:integer" use="optional"/>
    </xs:complexType>

    <xs:group name="interactant-group">
        <xs:sequence>
            <xs:element name="id" type="xs:string"/>
            <xs:element name="name" type="xs:string"/>
            <xs:element name="organism" type="xs:string"/>
            <xs:element name="actions" type="action-list-type"/>
            <xs:element name="references" type="reference-list-type"/>
            <xs:element name="known-action" type="known-action-type"/>
            <xs:element maxOccurs="unbounded" minOccurs="0" name="polypeptide" type="polypeptide-type"/>
        </xs:sequence>
    </xs:group>

    <xs:complexType name="polypeptide-type">
        <xs:sequence>
            <xs:element name="name" type="xs:string"/>
            <xs:element name="general-function" type="xs:string"/>
            <xs:element name="specific-function" type="xs:string"/>
            <xs:element name="gene-name" type="xs:string"/>
            <xs:element name="locus" type="xs:string"/>
            <xs:element name="cellular-location" type="xs:string"/>
            <xs:element name="transmembrane-regions" type="xs:string"/>
            <xs:element name="signal-regions" type="xs:string"/>
            <xs:element name="theoretical-pi" type="xs:string"/>
            <xs:element name="molecular-weight" type="xs:string"/>
            <xs:element name="chromosome-location" type="xs:string"/>
            <xs:element name="organism">
                <xs:complexType>
                    <xs:simpleContent>
                    <xs:extension base="xs:string">
                        <xs:attribute name="ncbi-taxonomy-id" type="xs:string"/>
                    </xs:extension>
                </xs:simpleContent>
            </xs:complexType>
            </xs:element>
            <xs:element name="external-identifiers" type="polypeptide-external-identifier-list-type"/>
            <xs:element name="synonyms" type="polypeptide-synonym-list-type"/>
            <xs:element name="amino-acid-sequence" type="sequence-type" minOccurs="1"/>
            <xs:element name="gene-sequence" type="sequence-type" minOccurs="1"/>
            <xs:element name="pfams" type="pfam-list-type"/>
            <xs:element name="go-classifiers" type="go-classifier-list-type"/>
        </xs:sequence>
        <xs:attribute name="id" type="xs:string" use="required"/>
        <xs:attribute name="source" type="xs:string" use="required"/>
    </xs:complexType>
    """

    @declared_attr
    def id(cls):
        """Disable id-autogeneration"""
        return None

    gene_id = db.Column(db.Integer, db.ForeignKey(Gene.id), primary_key=True)
    drug_id = db.Column(db.Integer, db.ForeignKey(Drug.id), primary_key=True)

    # usually it is just a single action
    actions = db.Column(ScalarSet(), default=set)

    gene = db.relationship(Gene, backref='targeted_by')
    drug = db.relationship(Drug, backref='targets')
