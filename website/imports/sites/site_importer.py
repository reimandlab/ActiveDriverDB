import warnings
from abc import abstractmethod
from typing import List, Set
from warnings import warn
from collections import Counter

from numpy import nan
from pandas import DataFrame, Series
from sqlalchemy.orm import load_only, joinedload
from tqdm import tqdm

from database import get_or_create, create_key_model_dict
from imports import Importer, protein_data as importers
# those should be moved somewhere else
from imports.protein_data import get_preferred_gene_isoform
from imports.sites.site_mapper import SiteMapper
from models import KinaseGroup, Kinase, Protein, Site, SiteType, BioModel, SiteSource, Gene


def show_warning(message, category, filename, lineno, file=None, line=None):
    print(message)


warnings.showwarning = show_warning


def get_or_create_kinases(chosen_kinases_names, known_kinases, known_kinase_groups):
    """Create a subset of known kinases and known kinase groups based on given
    list of kinases names ('chosen_kinases_names'). If no kinase or kinase group
    of given name is known, it will be created.

    Returns a tuple of sets:
        kinases, groups
    """
    kinases, groups = set(), set()

    for name in set(chosen_kinases_names):

        # handle kinases group
        if name.endswith('_GROUP'):
            name = name[:-6]
            if name not in known_kinase_groups:
                known_kinase_groups[name] = KinaseGroup(name=name)
            groups.add(known_kinase_groups[name])
        # if it's not a group, it surely is a kinase:
        else:
            if name not in known_kinases:
                known_kinases[name] = Kinase(
                    name=name,
                    protein=get_preferred_gene_isoform(name)
                )
            kinases.add(known_kinases[name])

    return kinases, groups


class SiteImporter(Importer):

    requires = {importers.kinase_mappings, importers.proteins_and_genes}

    # used for cross-isoform mapping
    sequence_offset = 7

    @property
    @abstractmethod
    def source_name(self) -> str:
        """A name of the source used to import sites"""

    @property
    @abstractmethod
    def site_types(self) -> Set[str]:
        """List of SiteTypes to be created (or re-used by the importer)"""

    def __init__(self):

        print(f'Preparing {self.source_name} sites importer...')

        self.issues_counter = Counter()
        # caching proteins and kinases allows for much faster
        # import later on, though it takes some time to cache
        self.known_kinases = create_key_model_dict(Kinase, 'name')
        self.known_groups = create_key_model_dict(KinaseGroup, 'name')
        self.known_sites = create_key_model_dict(
            Site, ['protein_id', 'position', 'residue'],
            options=(
                joinedload(Site.sources).joinedload('*')
            )
        )
        self.proteins = create_key_model_dict(
            Protein, 'refseq',
            options=(
                load_only('refseq', 'sequence', 'id')
                .joinedload(Protein.gene)
                .joinedload(Gene.isoforms)
                .load_only('refseq')
            )
        )

        # create site types
        site_type_objects = [
            get_or_create(SiteType, name=name)
            for name in set(self.site_types)
        ]

        self.novel_site_types = [
            site_type for site_type, new in site_type_objects if new
        ]

        self.source, _ = get_or_create(SiteSource, name=self.source_name)

        print(f'{self.source_name} importer ready.')

    def load(self, *args, **kwargs) -> List[BioModel]:
        """Return a list of sites and site types to be added to the database"""

        self.issues_counter.clear()

        print('Loading protein sites:')

        objects = self.load_sites(*args, **kwargs) + self.novel_site_types + [self.source]

        for issue, count in self.issues_counter.items():
            print(f'Encountered {count} issues: "{issue}".')

        return objects

    @abstractmethod
    def load_sites(self, *args, **kwargs) -> List[Site]:
        """Return a list of sites to be added to the database"""

    def get_sequence_of_protein(self, site) -> str:
        protein = Protein.query.filter_by(refseq=site.refseq).one()
        return protein.sequence

    def extract_site_surrounding_sequence(self, site) -> str:
        """Creates a pattern for site mapping using:

            - ^ to indicate a site that is closer than 7 aa to N-terminal end (left end)
            - $ to indicate a site that is closer than 7 aa to C-terminal end (right end)
            - sequence of the protein retrieved with `get_sequence_of_protein` method,
            limited to +/- 7 aa from the position of the site (determined by site.position).

        The offset (default 7) can be adjusted changing `sequence_offset` class variable.
        """
        protein_sequence = self.get_sequence_of_protein(site)

        if not protein_sequence:
            self.issues_counter['no sequence'] += 1
            return nan

        offset = self.sequence_offset
        pos = site.position - 1

        if pos < 0 or pos > len(protein_sequence):
            self.issues_counter['site outside of sequence'] += 1
            warn(
                f'The site: {self.repr_site(site)} is outside of the protein'
                f' sequence (which is {len(protein_sequence)} long)'
            )
            return nan

        if protein_sequence[pos] != site.residue:
            self.issues_counter['sequence mismatch'] += 1
            warn(
                f'Protein sequence at {pos} ({protein_sequence[pos]})'
                f' differs from {site.residue} for: {self.repr_site(site)}.'
            )
            return nan

        left = pos - offset
        right = pos + offset + 1

        if left < 0:
            left = 0
            prefix = '^'
        else:
            prefix = ''

        if right > len(protein_sequence):
            return prefix + protein_sequence[left:] + '$'
        else:
            return prefix + protein_sequence[left:right]

    def determine_left_offset(self, site) -> int:
        """Return 0-based offset of the site position in extracted sequence fragment

        Example:
            having site 3R and sequence='MARSTS',
            the left offset is 2, as sequence[2] == 'R'
        """
        return min(site.position - 1, self.sequence_offset)

    def map_sites_to_isoforms(self, sites: DataFrame) -> DataFrame:
        if sites.empty:
            return sites

        # additional "sequence" column is needed to map the site across isoforms
        sequences = sites.apply(self.extract_site_surrounding_sequence, axis=1)
        offsets = sites.apply(self.determine_left_offset, axis=1)
        sites = sites.assign(sequence=Series(sequences), left_sequence_offset=Series(offsets))

        old_len = len(sites)
        sites.dropna(axis=0, inplace=True, subset=['sequence', 'residue'])
        diff = old_len - len(sites)
        print(f'Dropped {diff} ({diff/old_len * 100}%) sites due to lack of sequence or residue')

        # nothing to map
        if sites.empty:
            return sites

        mapper = SiteMapper(self.proteins, self.repr_site)

        # sites loaded so far were explicitly defined in data files
        mapped_sites = mapper.map_sites_by_sequence(sites)

        # from now, only sites which really appear in isoform sequences
        # in our database will be considered

        # forget about the sequence column (no longer need)
        mapped_sites.drop(columns=['sequence', 'left_sequence_offset'], inplace=True, errors='ignore')

        return mapped_sites

    def add_site(self, refseq, position: int, residue, mod_type, pubmed_ids=None, kinases=None):

        protein = self.proteins[refseq]
        site_key = (protein.id, position, residue)

        if site_key in self.known_sites:
            site = self.known_sites[site_key]
            created = False
        else:
            site = Site(
                position=position,
                residue=residue,
                protein_id=protein.id
            )
            self.known_sites[site_key] = site
            created = True

        site.type.add(mod_type)
        site.sources.add(self.source)

        if pubmed_ids:
            site.pmid.update(pubmed_ids)

        if kinases:
            site_kinases, site_kinase_groups = get_or_create_kinases(
                kinases,
                self.known_kinases,
                self.known_groups
            )
            site.kinases.update(site_kinases)
            site.kinase_groups.update(site_kinase_groups)

        return site, created

    def create_site_objects(
        self,
        sites: DataFrame,
        columns=['refseq', 'position', 'residue', 'mod_type', 'pub_med_ids', 'kinases']
    ) -> List[Site]:

        if sites.empty:
            return []

        sites = sites[columns]
        site_objects = []
        add_site = self.add_site

        print('Creating database objects:')

        for site_data in tqdm(sites.itertuples(index=False), total=len(sites)):

            site, new = add_site(*site_data)

            if new:
                site_objects.append(site)

        return site_objects

    @staticmethod
    def repr_site(site):
        return f'{site.position}{site.residue}'
