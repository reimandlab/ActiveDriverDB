import re
from typing import List
from warnings import warn

from pandas import DataFrame
from tqdm import tqdm

from database import create_key_model_dict
from models import Protein, Gene


def find_all(longer_string: str, sub_string: str):
    """Returns positions of all overlapping matches.

    Allowed alphabet excludes '^' and '$' characters.

    If sub_string starts with '^' or ends with '$'
    an exact match (at front or at the end) will
    be performed.
    """
    if sub_string.startswith('^'):
        # there can be only one match
        # (or otherwise we would be matching with
        # less precision than declared earlier)
        return [0] if longer_string.startswith(sub_string[1:]) else []
    if sub_string.endswith('$'):
        return [len(longer_string) - len(sub_string) + 1] if longer_string.endswith(sub_string[:-1]) else []

    position = -1
    matches = []

    while True:
        position = longer_string.find(sub_string, position + 1)

        if position == -1:
            return matches

        matches.append(position)


def find_all_regex(longer_string: str, sub_string: str):
    """Should have the same effect as `find_all`,

    but as it adds an overhead of creating match objects
    and has to supports a lot of additional features, is
    probably match slower than `find_all`
    """

    if not (sub_string.startswith('^') or sub_string.endswith('$')):
        # positive lookahead to enable detection of overlapping matches
        sub_string = '(?=' + sub_string + ')'

    return [
        match.start()
        for match in re.finditer(sub_string, longer_string)
    ]


class OneBasedPosition(int):
    pass


class SiteMapper:

    def __init__(self, proteins, repr_site):
        self.proteins = proteins
        self.repr_site = repr_site
        self.genes = create_key_model_dict(Gene, 'name')
        self.has_gene_names = None
        self.already_warned = None

    def map_sites_by_sequence(self, sites: DataFrame) -> DataFrame:
        """Given a site with an isoform it should occur in,
        verify if the site really appears on the given position
        in this isoform and find where in all other isoforms
        this site appears (by exact match of a sequence span,
        typically one 15 amino acids long: site position +/-7 aa).

        If a site does not appear on declared position in the
        original isoform, emit a warning and try to find the
        correct position (to overcome a potential sequence shift
        which might be a result of different sequence versions).

        If there is no isoform with given refseq and there is
        a gene column in provided sites DataFrame, all isoforms
        of this gene will be used for mapping.

        Args:
            sites: data frame with sites, having (at least) following columns:
                   'sequence', 'position', 'refseq', 'residue', 'left_sequence_offset'

        Returns:
            Data frame of sites mapped to isoforms in database,
            including the sites in isoforms provided on input,
            if those has been confirmed or adjusted.
        """
        print('Mapping sites to isoforms')

        mapped_sites = []
        self.already_warned = set()
        self.has_gene_names = 'gene' in sites.columns

        for site in tqdm(sites.itertuples(index=False), total=len(sites)):

            protein = None
            positions = {}

            isoforms_to_map = self.choose_isoforms_to_map(site)

            # find matches
            for isoform in isoforms_to_map:
                positions[isoform] = self.map_site_to_isoform(site, isoform)

            if protein:
                matches = positions[protein]
                self.collate_matches_with_expectations(matches, site)

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

    def map_site_to_isoform(self, site, isoform: Protein) -> List[OneBasedPosition]:
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
            # asterisks (*) representing stop codon are removed for the time of mapping
            # so expression like 'SOMECTERMINALSEQUENCE$' can be easily matched
            for m in find_all(isoform.sequence.rstrip('*'), site.sequence)
        ]

        if len(matches) > 1:
            warn(f'More than one match for: {self.repr_site(site)}')
        if any(abs(position - site.position) > len(isoform.sequence) / 2 for position in matches):
            warn(
                f'This site {self.repr_site(site)} was found on {matches} positions, '
                f'and some are quite far away from the position in '
                f'original isoform: {site.position}.'
            )

        return matches

    def choose_isoforms_to_map(self, site):
        protein = None

        if site.refseq not in self.proteins:
            if site.refseq not in self.already_warned:
                warn(f'No protein with {site.refseq} for {self.repr_site(site)}')
                self.already_warned.add(site.refseq)
            if self.has_gene_names and site.gene in self.genes:
                gene = self.genes[site.gene]
                warn(f'Using {gene} to map {self.repr_site(site)}')
            else:
                return []
        else:
            protein = self.proteins[site.refseq]
            gene = protein.gene

        if gene and gene.isoforms:
            return {self.proteins[isoform.refseq] for isoform in gene.isoforms}
        elif protein:
            return {protein}
        return []

    def collate_matches_with_expectations(self, original_isoform_matches, site):

        if not original_isoform_matches:
            warn(f'The site: {self.repr_site(site)} was not found in {site.refseq}, '
                 f'though it should appear in this isoform according to provided sites data.')
        elif all(match_pos != site.position for match_pos in original_isoform_matches):
            warn(f'The site: {self.repr_site(site)} does not appear on the exact given position in '
                 f'{site.refseq} isoform, though it was re-mapped to: {original_isoform_matches}.')
