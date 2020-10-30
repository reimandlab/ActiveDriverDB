import logging
import re
from collections import defaultdict
from typing import List
from warnings import warn

from pandas import DataFrame
from tqdm import tqdm

from database import create_key_model_dict
from models import Protein, Gene


logger = logging.getLogger(__name__)


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
                   'sequence', 'position', 'refseq', 'residue', 'left_sequence_offset';
                   and can provide optional 'gene' column

        Returns:
            Data frame of sites mapped to isoforms in database,
            including the sites in isoforms provided on input,
            if those has been confirmed or adjusted. An effort
            will be made to avoid mapping two sites to the same
            position, but lack of duplicates is not guaranteed
            and drop_duplicates() is advised at a later stage.
        """
        print('Mapping sites to isoforms')

        mapped_cnt = 0
        mapped_sites = []
        self.already_warned = set()
        self.has_gene_names = 'gene' in sites.columns

        known_sites_by_refseq = defaultdict(list)
        for site in sites.itertuples(index=False):
            known_sites_by_refseq[site.refseq].append(site)

        for site in tqdm(sites.itertuples(index=False), total=len(sites)):

            was_mapped = False
            protein = self.proteins.get(site.refseq, None)
            positions = {}

            isoforms_to_map = self.choose_isoforms_to_map(site)

            # find matches
            for isoform in isoforms_to_map:
                positions[isoform] = self.map_site_to_isoform(site, isoform)

            if protein:
                matches = positions[protein]
                self.compare_matches_with_expectations(matches, site)

            # create rows with sites
            for isoform, matched_positions in positions.items():

                # to check if any other of the sites is already mapped here;
                # note: it will not raise as it is a defaultdict
                input_sites_of_this_isoform = known_sites_by_refseq[isoform.refseq]

                for position in matched_positions:

                    # _replace() returns new namedtuple with replaced values;
                    # it is not protected but hidden (to allow 'replace' field)
                    new_site = site._replace(
                        refseq=isoform.refseq,
                        position=position
                    )

                    # NOTE: despite all hte effort below, duplicate results will happen,
                    # because the input site might be remapped to a slightly different
                    # place; that would be expensive to check, thus simple drop of
                    # duplicates at a later stage is advised
                    if (
                        # if a site were to be mapped to a place it was known to be at
                        # it shall not be repeated (to avoid duplicates)
                        any(
                            # note: using equality comparison as site tuple can contain
                            # non-hashable elements at this point
                            existing_site == new_site
                            for existing_site in input_sites_of_this_isoform
                        )
                        # however, if we are in the isoform from which we are mapping
                        # so mapping onto itself, we should allow such matches
                        # (as otherwise we would not get the source site!)
                        and
                        not (
                            isoform.refseq == protein.refseq
                            and
                            site.position == new_site.position
                        )
                    ):
                        # this site was already provided for this isoform at input,
                        # if we were to add it here, the sites would be duplicated
                        logger.info(
                            f'{self.repr_site(new_site)} was already provided'
                            f' for this isoform at input.'
                        )
                        continue

                    mapped_sites.append(new_site)
                    was_mapped = True

            if was_mapped:
                mapped_cnt += 1

        print(
            f'Successfully mapped {mapped_cnt} out of {len(sites)} '
            f'({mapped_cnt / len(sites) * 100:.2f}%) sites,'
            f' to the total of {len(mapped_sites)} site objects. '
            f' Each site was on average mapped to'
            f' {len(mapped_sites) / len(sites):.2f} isoforms.'
        )

        return DataFrame(mapped_sites)

    def map_site_to_isoform(self, site, isoform: Protein) -> List[OneBasedPosition]:
        """Finds all occurrences of a site (by exact sequence match)
        in provided sequence of an alternative isoform.

        Original position of the site is used to highlight "suspicious" cases,
        in which the matched site is far away (>50/90% of isoform length) from
        the one of the original site. This is based on premise that most of
        alternative isoform should not differ so much.

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

        if matches:
            biggest_distance = max(abs(position - site.position) for position in matches)

            if biggest_distance > len(isoform.sequence) / 2:
                positions = ", ".join([str(m) for m in matches])

                if biggest_distance > len(isoform.sequence) * 9 / 10:
                    inform = warn
                else:
                    inform = logger.info

                inform(
                    f'Site {self.repr_site(site)} was found on position(s): '
                    f'{positions}; some are quite far away from the '
                    f'position in original isoform: {site.position}.'
                )

        return matches

    def choose_isoforms_to_map(self, site):
        protein = None

        if site.refseq not in self.proteins:
            if self.has_gene_names and site.gene in self.genes:
                gene = self.genes[site.gene]
                logger.info(
                    f'Using {gene} to map {self.repr_site(site)} (not using '
                    f'{site.refseq}, as this sequence is not available).'
                )
            else:
                if site.refseq not in self.already_warned:
                    warn(
                        f'No protein with {site.refseq} '
                        + (f'and no gene named {site.gene} ' if self.has_gene_names else '') +
                        f'(first encountered for {self.repr_site(site)}).'
                    )
                    self.already_warned.add(site.refseq)
                return []
        else:
            protein = self.proteins[site.refseq]
            gene = protein.gene

        if gene and gene.isoforms:
            return {self.proteins[isoform.refseq] for isoform in gene.isoforms}
        elif protein:
            return {protein}
        return []

    def compare_matches_with_expectations(self, original_isoform_matches, site):

        if not original_isoform_matches:
            warn(f'Site: {self.repr_site(site)} was not found in {site.refseq}, '
                 f'though it should appear in this isoform according to provided sites data.')
        elif all(match_pos != site.position for match_pos in original_isoform_matches):
            warn(f'Site: {self.repr_site(site)} does not appear on the exact given position in '
                 f'{site.refseq} isoform, though it was re-mapped to: {original_isoform_matches}.')
