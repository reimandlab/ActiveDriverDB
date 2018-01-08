from typing import List
from warnings import warn

from pandas import DataFrame
from tqdm import tqdm

from models import Protein


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


class SiteMapper:

    def __init__(self, proteins, repr_site):
        self.proteins = proteins
        self.repr_site = repr_site

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
                positions[isoform] = self.map_site_to_isoform(site, isoform)

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
            for m in find_all(isoform.sequence, site.sequence)
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
