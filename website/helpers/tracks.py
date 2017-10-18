"""
Group of classes useful to generate tracks like sequence, mutations etc.
"""
from collections import defaultdict
from collections import OrderedDict


class Track(object):
    """Whole track with its elements and subtracts"""

    def __init__(self, name, elements, subtracks='', inline=False):
        """
        inline: tells if the track is a subtract which
        should be nested under the parent Track

        elements: list of TrackElements or a string
        """
        self.name = name
        self.elements = elements
        self.subtracks = subtracks
        self.inline = inline

    @property
    def class_name(self):
        """Class names to be used in CSS and DOM"""
        classes = [self.name]
        if not self.elements:
            classes.append('empty')
        if self.inline:
            classes.append('inline')
        return ' '.join(classes)

    @property
    def display_name(self):
        """A name or hard space for unnamed tracks"""
        return self.name if self.name else '&nbsp;'


class TrackElement(object):
    """Single element like mutation, phosporylation site etc on a track.

    It is used a lot for every single protein, hence __slots__ implemented.
    """

    __slots__ = 'start', 'length', 'name', 'description'

    def __init__(self, start, length, name='', description=''):
        assert start >= 0
        self.start = start
        self.length = length
        self.name = name
        self.description = description

    @property
    def shown_name(self):
        """Generates a name which will fit into a track."""
        if not self.description:
            return self.name or ''

        # names_to_try should be kept in descending length order
        names_to_try = (
            '%s: %s (%d long)' % (self.name, self.description, self.length),
            '%s: %s' % (self.name, self.description),
            '%s' % self.name
        )
        for name in names_to_try:
            if len(name) <= self.length:
                return name

        # if no proposed name fits, use the last one (shortest)
        return names_to_try[-1]


class SequenceTrack(Track):

    def __init__(self, protein):

        self.protein = protein
        self.length = protein.length

        subtracks = self.ptm_sites_subtracks()

        super().__init__('sequence', protein.sequence, subtracks)

    def ptm_sites_subtracks(self):

        # store in descending order or use z-index
        spans = (7, 3)
        ptm_site_ranges = {}

        for shift in spans:
            size = 2 * shift + 1

            coords = [
                [site.position - shift, size]
                for site in self.protein.sites
            ]
            self.trim_ends(coords)

            ptm_site_ranges[shift] = [
                TrackElement(start, length)
                for start, length in coords
            ]

        return [
            Track('ptm_site_' + str(shift), ptm_site_ranges[shift], inline=True)
            for shift in spans
        ]

    def trim_ends(self, elements):
        """Trim coordinates defining TrackElements to fit into the track.
        Test with: NM_024666

        Args:
            elements: sorted list of elements positions (tuples: start, end).
        """
        if not elements:
            return

        # do not exceed 0 on the beginning
        for i, element_data in enumerate(elements):
            start, length = element_data

            # this element and all consecutive elements are not lower than 0
            if start > 0:
                break

            # set start to the first position
            elements[i][0] = 1
            # and update length
            elements[i][1] = length + start - 1    # start is negative

        # and do not exceed sequence length at the end
        for i, element_data in enumerate(reversed(elements)):
            start, length = element_data

            if start + length <= self.length:
                break

            # set length
            elements[-i - 1][1] = self.length - start + 1


class DomainsTrack(Track):

    collapsed = True

    def __init__(self, domains):

        tracks = OrderedDict()

        grouped_domains = self.group_domains(domains)

        consensus_track = []

        for level, domains in grouped_domains.items():
            tracks[level] = list(map(self.make_element, domains))

            for domain in domains:
                # if parent of element is already here, try to extend it
                for consensus_domain in consensus_track:
                    consensus_interpro = consensus_domain.interpro

                    checked_interpro = domain.interpro
                    hit = False
                    while checked_interpro.parent:
                        if consensus_interpro == checked_interpro.parent:
                            hit = True
                            break
                        checked_interpro = checked_interpro.parent

                    if hit:
                        consensus_domain.start = min(
                            consensus_domain.start, domain.start
                        )
                        consensus_domain.end = max(
                            consensus_domain.end, domain.end
                        )
                        break
                else:
                    consensus_track.append(domain)

        levels = list(tracks.keys())

        subtracks = [
            Track('', tracks[level])
            for level in levels
        ]

        super().__init__(
            'domains',
            map(self.make_element, consensus_track),
            subtracks
        )

    def make_element(self, domain):
        return TrackElement(
            domain.start,
            domain.end - domain.start,
            domain.interpro.accession,
            domain.interpro.description
        )

    def group_domains(self, domains):

        grouped = defaultdict(list)
        for domain in domains:
            level = domain.interpro.level
            if not level:
                level = 0
            grouped[level].append(domain)

        grouped_and_sorted = OrderedDict()
        levels = list(grouped.keys())
        for level in sorted(levels):
            grouped_and_sorted[level] = grouped[level]

        return grouped_and_sorted


class MutationsTrack(Track):

    def __init__(self, raw_mutations):

        tracks = []
        for mutations in self.group_mutations(raw_mutations):
            track = [
                TrackElement(mutation.position, 1, mutation.alt)
                for mutation in mutations.values()
            ]
            tracks.append(track)

        subtracks = [Track('', muts) for muts in tracks[1:]]

        super().__init__('mutations', tracks[0], subtracks)

    def group_mutations(self, mutations):

        grouped = [{}]
        for mutation in mutations:
            depth = 0
            pos = mutation.position
            try:
                while pos in grouped[depth]:
                    if grouped[depth][pos].alt == mutation.alt:
                        # TODO: increase frequency count
                        break
                    depth += 1
            except IndexError:
                grouped.append({})
            grouped[depth][pos] = mutation

        return grouped

