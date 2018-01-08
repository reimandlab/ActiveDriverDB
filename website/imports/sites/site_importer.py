from abc import abstractmethod
from typing import List, Set
from warnings import warn

from numpy import nan
from pandas import DataFrame, Series
from sqlalchemy.orm import load_only, joinedload
from tqdm import tqdm

from database import get_or_create, create_key_model_dict
from imports import Importer, protein_data as importers
# those should be moved somewhere else
from imports.protein_data import get_preferred_gene_isoform
from models import KinaseGroup, Kinase, Protein, Site, SiteType, BioModel, SiteSource, Gene


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


def find_all(longer_string: str, sub_string: str):
    """Returns positions of all overlapping matches"""
    position = -1
    matches = []

    while True:
        position = longer_string.find(sub_string, position + 1)

        if position == -1:
            return matches

        matches.append(position)


class OneBasedPosition(int):
    pass


def map_site_to_isoform(site, isoform: Protein) -> List[OneBasedPosition]:
    """Finds all occurrences of a site (by exact sequence match)
    in provided sequence of an alternative isoform.

    Original position of the site is used to highlight "suspicious" cases,
    in which the matched site is far away (>50% of isoform length) from
    the one of the original site. This is based on premise that most of
    alternative isoform does not differ by more than 50% (TODO: prove this)

    Returned positions are 1-based
    """
    matches = [
        m + 1 + site.left_sequence_offset
        for m in find_all(isoform.sequence, site.sequence)
    ]

    if len(matches) > 1:
        warn(f'More than one match for: {site}')
    if any(abs(position - site.position) > len(isoform.sequence) / 2 for position in matches):
        warn(
            f'This site {site} was found on {matches} positions, '
            f'and some are quite far away from the position in '
            f'original isoform: {site.position}.'
        )

    return matches


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
        print('Loading protein sites:')

        return self.load_sites(*args, **kwargs) + self.novel_site_types + [self.source]

    @abstractmethod
    def load_sites(self, *args, **kwargs) -> List[Site]:
        """Return a list of sites to be added to the database"""

    def get_sequence_of_protein(self, site) -> str:
        protein = Protein.query.filter_by(refseq=site.refseq).one()
        return protein.sequence

    def extract_site_surrounding_sequence(self, site) -> str:
        """site.position is always 1-based"""
        protein_sequence = self.get_sequence_of_protein(site)

        if not protein_sequence:
            return nan

        offset = self.sequence_offset
        pos = site.position - 1

        if pos < 0 or pos > len(protein_sequence):
            warn(
                f'The site: {self.repr_site(site)} is outside of the protein'
                f' sequence (which is {len(protein_sequence)} long)'
            )
            return nan

        if protein_sequence[pos] != site.residue:
            warn(
                f'Protein sequence at {pos} ({protein_sequence[pos]})'
                f' differs from {site.residue} for site: {site}.'
            )
            return nan

        return protein_sequence[
           max(pos - offset, 0)
           :
           min(pos + offset + 1, len(protein_sequence))
        ]

    def determine_left_offset(self, site) -> int:
        """Return 0-based offset of the site position in extracted sequence fragment

        Example:
            having site 3R and sequence='MARSTS',
            the left offset is 2, as sequence[2] == 'R'
        """
        return min(site.position - 1, self.sequence_offset)

    def map_sites_to_isoforms(self, sites: DataFrame) -> DataFrame:
        # additional "sequence" column is needed to map the site across isoforms
        sequences = sites.apply(self.extract_site_surrounding_sequence, axis=1)
        offsets = sites.apply(self.determine_left_offset, axis=1)
        sites = sites.assign(sequence=Series(sequences), left_sequence_offset=Series(offsets))

        old_len = len(sites)
        sites.dropna(axis=0, inplace=True, subset=['sequence', 'residue'])
        print(f'Dropped {old_len - len(sites)} sites due to lack of sequence or residue')

        # nothing to map
        if len(sites) == 0:
            return sites

        # sites loaded so far were explicitly defined in data files
        mapped_sites = self._map_sites_by_sequence(sites)

        # from now, only sites which really appear in isoform sequences
        # in our database will be considered

        # forget about the sequence column (no longer need)
        mapped_sites.drop(columns=['sequence', 'left_sequence_offset'], inplace=True, errors='ignore')

        return mapped_sites

    def _map_sites_by_sequence(self, sites: DataFrame) -> DataFrame:
        """Given a site with an isoform it should occur in,
        verify if the site really appears on the given position
        in this isoform and find where in all other isoforms
        given site appears (by exact match of +/-7 sequence span).

        If a site does not appear on declared position in the
        original isoform, emit a warning and try to find the
        correct position (to overcome a potential sequence shift
        which might be a result of different sequence versions).

        Args:
            sites: data frame with sites, having (at least) following columns:
                   'sequence', 'position', 'refseq', 'residue', 'sequence_left_offset'

        Returns:
            Data frame of sites mapped to isoforms in database,
            including the sites in isoforms provided on input,
            if those has been confirmed or adjusted.
        """
        print('Mapping sites to isoforms')

        mapped_sites = []
        already_warned = set()

        for site in tqdm(sites.itertuples(index=False), total=len(sites)):

            site_id = self.repr_site(site)

            if site.refseq not in self.proteins:
                if site.refseq not in already_warned:
                    warn(f'No protein with {site.refseq} for {site_id}')
                    already_warned.add(site.refseq)
                # TODO: fallback to gene directly (if there is site.gene, try it)
                continue

            protein = self.proteins[site.refseq]

            gene = protein.gene

            if gene and gene.isoforms:
                isoforms_to_map = {self.proteins[isoform.refseq] for isoform in gene.isoforms}
            else:
                isoforms_to_map = {protein}

            positions = {}

            # find matches
            for isoform in isoforms_to_map:
                positions[isoform] = map_site_to_isoform(site, isoform)

            original_isoform_matches = positions[protein]

            if not original_isoform_matches:
                warn(f'The site: {site_id} was not found in {protein.refseq}, '
                     f'though it should appear in this isoform according to provided sites data.')
            elif all(match_pos != site.position for match_pos in original_isoform_matches):
                warn(f'The site: {site_id} does not appear on the exact given position in '
                     f'{protein.refseq} isoform, though it was re-mapped to: {original_isoform_matches}.')

            # create rows with sites
            for isoform, matched_positions in positions.items():

                if not matched_positions:
                    continue

                for position in matched_positions:

                    # _replace() returns new namedtuple with replaced values;
                    # it is not protected but hidden (to allow 'replace' field)
                    new_site = site._replace(
                        refseq=isoform.refseq,
                        position=position
                    )
                    mapped_sites.append(new_site)

        return DataFrame(mapped_sites)

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
