from abc import abstractmethod
from copy import copy
from warnings import warn

from pandas import DataFrame
from tqdm import tqdm

from database import get_or_create
from imports import Importer, protein_data as importers
# those should be moved somewhere else
from imports.protein_data import get_preferred_gene_isoform, create_key_model_dict
from models import KinaseGroup, Kinase, Protein, Site, SiteType


def get_or_create_kinases(chosen_kinases_names, known_kinases, known_kinase_groups):
    """Create a subset of known kinases and known kinase groups based on given
    list of kinases names ('chosen_kinases_names'). If no kinase or kinase group
    of given name is known, it will be created.

    Returns a tuple of sets:
        kinases, groups
    """
    kinases, groups = set(), set()

    for name in list(set(chosen_kinases_names)):

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


def map_site_to_isoform(site, isoform: Protein):
    """Finds all occurrences of a site (by exact sequence match)
    in provided sequence of an alternative isoform.

    Original position of the site is used to highlight "suspicious" cases,
    in which the matched site is far away (>50% of isoform length) from
    the one of the original site. This is based on premise that most of
    alternative isoform does not differ by more than 50% (TODO: prove this)
    """
    matches = find_all(isoform.sequence, site.sequence)

    if len(matches) > 1:
        warn('More than one match for: {site}'.format(site=site))
    if any(abs(position - site.position) > len(isoform.sequence) / 2 for position in matches):
        warn('This site quite far away from the original site.')

    return matches


class SiteImporter(Importer):

    requires = {importers.kinase_mappings, importers.proteins_and_genes}

    # used for cross-isoform mapping
    sequence_offset = 7

    @property
    @abstractmethod
    def site_types(self):
        return []

    def __init__(self):
        self.known_kinases = create_key_model_dict(Kinase, 'name')
        self.known_groups = create_key_model_dict(KinaseGroup, 'name')
        self.proteins = create_key_model_dict(Protein, 'refseq')

        # create site types
        site_type_objects = [get_or_create(SiteType, name=name) for name in self.site_types]

        self.types_map = {
            site_type.name: site_type
            for site_type, new in site_type_objects
        }

        self.novel_site_types = [
            site_type for site_type, new in site_type_objects if new
        ]

    def load(self, *args, **kwargs):
        """Return a list of sites and site types to be added to the database"""
        print('Loading protein sites:')

        return self.load_sites(*args, **kwargs) + self.novel_site_types

    @abstractmethod
    def load_sites(self, *args, **kwargs):
        """Return a list of sites to be added to the database"""

    def get_sequence_of_protein(self, site):
        protein = Protein.query.filter_by(refseq=site.refseq).one()
        return protein.sequence

    def extract_site_surrounding_sequence(self, site):
        protein_sequence = self.get_sequence_of_protein(site)

        # TODO: add residue verification
        offset = self.sequence_offset

        return protein_sequence[max(site.position - offset, 0):min(site.position + offset, len(protein_sequence))]

    def determine_left_offset(self, site):
        return min(site.position, self.sequence_offset)

    def map_sites_to_isoforms(self, sites):
        """"""
        print('Mapping sites to isoforms')

        new_sites = []

        for _, site in tqdm(sites):

            if site.refseq not in self.proteins:
                warn('No protein with {site.refseq}'.format(site=site))
                continue

            protein = self.proteins[site.refseq]
            gene = protein.gene

            if not gene or not gene.isoforms:
                continue

            # TODO: Probably this should not relay on
            # TODO: the provided protein (as the sequence
            # TODO: might use different version) but map
            # TODO: to all isoforms (from scratch)
            # TODO: and then warn if there is any discrepancy
            isoforms_to_map = set(gene.isoforms) - {protein}

            for isoform in isoforms_to_map:
                matched_positions = map_site_to_isoform(site, isoform)

                if not matched_positions:
                    continue

                new_site = copy(site)
                new_site.refseq = isoform.refseq

                for position in matched_positions:

                    new_site.position = position + site.left_sequence_offset

                    new_sites.append(
                        new_site
                    )

        return DataFrame(new_sites)

    def add_site(self, refseq, position: int, residue, mod_type, pubmed_ids, kinases=None):

        site_kinases, site_kinase_groups = get_or_create_kinases(
            kinases,
            self.known_kinases,
            self.known_groups
        )

        site, created = get_or_create(
            Site,
            position=position,
            residue=residue,
            protein=self.proteins[refseq]
        )

        site.type.add(mod_type)
        site.pmid.update(pubmed_ids)

        site.kinases.extend(site_kinases)
        site.kinase_groups.extend(site_kinase_groups)

        return site, created
