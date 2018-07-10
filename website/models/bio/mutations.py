from abc import ABCMeta, abstractmethod
from collections import UserList, OrderedDict
from functools import lru_cache
from typing import Type, Iterable, Mapping, List, Dict

from sqlalchemy import select, func, or_, and_, exists
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.hybrid import hybrid_property, Comparator, hybrid_method
from sqlalchemy.orm import synonym, RelationshipProperty

from database import db
from helpers.models import generic_aggregator

from .diseases import ClinicalData
from .model import BioModel, make_association_table
from .sites import Site, SiteMotif


class MutationDetailsManager(UserList, metaclass=ABCMeta):
    """Groups (by a unique mutation) mutation details from a given source"""

    @property
    @abstractmethod
    def name(self) -> str:
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

            return {'Cancers': cancer_occurrences}

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
    def name(self) -> str:
        """Internal name which has to remain unchanged, used in relationships"""
        raise NotImplementedError

    @property
    def is_confirmed(self):
        """Does this mutation come from an experiment (True) or it is a prediction (False)?"""
        return True

    @property
    def is_visible(self):
        """Should this mutation be shown to the user?"""
        return True

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


MutationSource = Type[MutationDetails]


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

    # user mutations should be visible in interface,
    # but should not be included in whole-proteome analyses
    is_confirmed = False

    value_type = 'count'

    def __init__(self, **kwargs):
        self.count = kwargs.pop('count', 0)
        super().__init__(**kwargs)

    # having count not mapped with SQLAlchemy prevents useless attempts
    # to update records which are not stored in database at all:
    # count = db.Column(db.Integer, default=0)
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


class PCAWGMutation(CancerMutation, BioModel):
    """Metadata for cancer mutations from PCAWG project"""
    name = 'PCAWG'
    display_name = 'Cancer (PCAWG)'
    details_manager = create_cancer_meta_manager('PCAWG')
    pcawg_cancer_code = association_proxy('cancer', 'code')
    cancer_code = pcawg_cancer_code


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
    disease_id = association_proxy('clin_data', 'disease_id')

    def get_value(self, filter=lambda x: x):
        return len(filter(self.clin_data))

    @hybrid_property
    def count(self):
        return self.get_value()

    @count.expression
    def count(cls):
        return (
            select([func.count(ClinicalData.id)])
            .where(ClinicalData.inherited_id == cls.id)
            .label('count')
        )

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

    @classmethod
    def significance_filter(cls, mode):
        significance_to_code = {
            significance: code
            for code, significance in ClinicalData.significance_codes.items()
        }
        return cls.clin_data.any(ClinicalData.sig_code.in_([
            significance_to_code[sig]
            for sig in ClinicalData.significance_subsets[mode]
        ]))


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
    scale = 1

    def get_value(self, filter=lambda x: x):
        """Total MAF in percents"""
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

    scale = 100

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
        json = {
            'MAF': self.maf_all,
            'MAF EAS': self.maf_eas,
            'MAF AMR': self.maf_amr,
            'MAF AFR': self.maf_afr,
            'MAF EUR': self.maf_eur,
            'MAF SAS': self.maf_sas,
        }
        return {
            name: (maf * self.scale if maf else None)
            for name, maf in json.items()
        }

    def get_value(self, filter=lambda x: x):
        return self.maf_all * self.scale

    populations_1KG = synonym('affected_populations')


class MIMPMutation(ManagedMutationDetails, BioModel):
    """Metadata for MIMP mutation"""

    name = 'MIMP'
    display_name = 'MIMP'
    is_confirmed = False
    is_visible = False

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


class Sources:

    def __init__(self, all_sources):
        self.all = all_sources

        self.relationships = {
            'meta_' + source.name: (
                managed_mutation_details_relationship(source)
                if are_details_managed(source) else
                mutation_details_relationship(source)
            )
            for source in all_sources
        }

        self.visible: List[MutationSource] = [
            source for source in all_sources if source.is_visible
        ]
        self.confirmed: List[MutationSource] = [
            source for source in all_sources if source.is_confirmed
        ]

        self.fields: Mapping[MutationSource, str] = {
            source: 'meta_' + source.name
            for source in all_sources
        }

        self.visible_fields: Mapping[str, str] = {
            source.name: 'meta_' + source.name
            for source in self.visible
        }

    def get_relationship(self, source: MutationSource) -> RelationshipProperty:
        return self.class_relation_map[source]

    def get_bound_relationship(self, mutation, source: MutationSource) -> MutationDetails:
        return getattr(mutation, self.fields[source])

    @property
    @lru_cache()
    def class_relation_map(self) -> Dict[MutationSource, RelationshipProperty]:
        return {
            model: getattr(Mutation, self.fields[model])
            for model in self.all
        }

    @property
    @lru_cache()
    def source_by_name(self) -> Dict[str, MutationSource]:
        return {
            model.name: model
            for model in self.all
        }


source_manager = Sources([
    # order matters (widget's labels will show up in this order)
    # TCGAMutation,
    MC3Mutation,
    PCAWGMutation,
    InheritedMutation,
    ExomeSequencingMutation,
    The1000GenomesMutation,
    UserUploadedMutation,
    MIMPMutation
])


class MutatedMotifs:

    were_affected_motifs_precomputed = db.Column(db.Boolean, default=False)

    @declared_attr
    def precomputed_affected_motifs(self):
        mutation_motif_table = make_association_table(f'{self.__tablename__}.id', SiteMotif.id)
        return db.relationship(
            SiteMotif,
            secondary=mutation_motif_table,
            collection_class=set,
            backref='mutations'
        )

    def affected_motifs(self, sites: Iterable[Site]=None):
        if self.were_affected_motifs_precomputed:
            return self.precomputed_affected_motifs

        from analyses.motifs import mutate_sequence
        from analyses.motifs import has_motif

        affected_motifs = []

        if not sites:
            sites = self.affected_sites

        for site in sites:
            for site_type in site.types:

                for motif in site_type.motifs:

                    if site.has_motif(motif.pattern):
                        # todo: make it a method of mutation? "self.mutate_sequence()" ?

                        mutated_sequence = mutate_sequence(site, self, offset=7)
                        if not has_motif(mutated_sequence, motif.pattern):
                            affected_motifs.append((motif, self.position - site.position + 7))

        return affected_motifs


class Mutation(BioModel, MutatedMotifs):
    __table_args__ = (
        db.Index('mutation_index', 'alt', 'protein_id', 'position'),
        db.UniqueConstraint('alt', 'protein_id', 'position')
    )

    # 1-based
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

    types = ('direct', 'network-rewiring', 'motif-changing', 'proximal', 'distal', 'none')

    vars().update(source_manager.relationships)

    populations_1KG = details_proxy(The1000GenomesMutation, 'affected_populations', managed=True)
    populations_ESP6500 = details_proxy(ExomeSequencingMutation, 'affected_populations', managed=True)
    mc3_cancer_code = details_proxy(MC3Mutation, 'mc3_cancer_code')
    pcawg_cancer_code = details_proxy(PCAWGMutation, 'pcawg_cancer_code')
    sig_code = details_proxy(InheritedMutation, 'sig_code')
    disease_id = details_proxy(InheritedMutation, 'disease_id')
    disease_name = details_proxy(InheritedMutation, 'disease_name')

    def __repr__(self):
        return '<Mutation in {0}, at {1} aa, substitution to: {2}>'.format(
            self.protein.refseq if self.protein else '-',
            self.position,
            self.alt
        )

    @hybrid_property
    def sources_map(self) -> Mapping[str, MutationDetails]:
        """Return mapping: name -> bound relationship for >confirmed< sources that mention this mutation"""
        mapping = {}
        for source in source_manager.confirmed:
            details = source_manager.get_bound_relationship(self, source)
            if details:
                mapping[source.name] = details
        return mapping

    @hybrid_property
    def sources(self) -> List[str]:
        """Return list of names of >visible< sources that mention this mutation"""
        return [
            source.name
            for source in source_manager.visible
            if source_manager.get_bound_relationship(self, source)
        ]

    @hybrid_property
    def is_confirmed(self):
        """Mutation is confirmed if there are metadata from one of four studies

        (or experiments). Presence of MIMP metadata does not imply
        if mutation has been ever studied experimentally before.
        """
        return any([source_manager.get_bound_relationship(self, source) for source in source_manager.confirmed])

    @is_confirmed.expression
    def is_confirmed(cls):
        """SQL expression for is_confirmed"""
        return or_(
            relationship_field.any()
            if relationship_field.prop.uselist
            else relationship_field.has()
            for relationship_field in [
                source_manager.get_relationship(source) for source in source_manager.confirmed
            ]
        )

    @hybrid_property
    def sites(self):
        return self.get_affected_ptm_sites()

    @sites.expression
    def sites(self):
        return self.affected_sites

    affected_sites = db.relationship(
        'Site',
        primaryjoin=(
            'and_('
            '   foreign(Site.protein_id) == Mutation.protein_id,'
            '   Site.position.between(Mutation.position - 7, Mutation.position + 7)'
            ')'
        ),
        order_by='Site.position'
    )

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

        return sorted(sites_affected, key=lambda site: site.position)

    def impact_on_specific_ptm(self, site: Site, ignore_mimp=False):
        if self.position == site.position:
            return 'direct'
        elif site in self.meta_MIMP.sites and not ignore_mimp:
            return 'network-rewiring'
        elif self.affected_motifs([site]):
            return 'motif-changing'
        elif abs(self.position - site.position) < 3:
            return 'proximal'
        elif abs(self.position - site.position) < 8:
            return 'distal'
        else:
            return 'none'

    def impact_on_ptm(self, site_filter=None):
        """How intense might be an impact of the mutation on a PTM site.

        It describes impact on the closest PTM site or on a site chosen by
        MIMP algorithm (so it applies only when 'network-rewiring' is returned)
        """
        if site_filter is None:
            sites = self.sites
        else:
            sites = site_filter(self.sites)

        if self.is_close_to_some_site(0, 0, sites):
            return 'direct'
        elif any(site in sites for site in self.meta_MIMP.sites):
            return 'network-rewiring'
        elif self.affected_motifs(sites):
            return 'motif-changing'
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
        return f'{self.ref}{self.position}{self.alt}'

    @property
    def name(self):
        return f'{self.protein.gene.name} {self.short_name}'

    def to_json(self):
        return {
            'name': self.name,
            'is_confirmed': self.is_confirmed,
            'is_ptm': self.is_ptm()
        }

    @classmethod
    def in_sources(cls, *sources: MutationSource, conjunction=and_):

        return conjunction(
            (
                (
                    source_manager.get_relationship(source).any()
                    if are_details_managed(source) else
                    source_manager.get_relationship(source).has()
                )
                for source in sources
            )
        )


