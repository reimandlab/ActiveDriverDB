"""
Group of classes useful to generate tracks like sequence, mutations etc.
"""


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
        return ' '.join(classes)

    @property
    def display_name(self):
        """A name or hard space for unnamed tracks"""
        return self.name if self.name else '&nbsp;'


class TrackElement(object):
    """Single element like mutation, phosporylation site etc on a track.

    It is used a lot for every single protein, hence __slots__ implemented.
    """

    __slots__ = 'start', 'length', 'name'

    def __init__(self, start, length, name=''):
        assert start >= 0
        self.start = start
        self.length = length
        self.name = name


class SequenceTrack(Track):

    def __init__(self, protein):

        self.protein = protein
        self.length = protein.length
        # mutatated_residues = [TrackElement(mutation.position, 1) for mutation in protein.mutations]

        subtracks = self.phosporylation_subtracks()

        super().__init__('sequence', protein.sequence, subtracks)

    def phosporylation_subtracks(self):

        # store in descending order or use z-index
        spans = (7, 3)
        phos_span = {}
        for size in spans:
            phos_span[size] = []

        for size in spans:
            shift = (size - 1) / 2
            for site in self.protein.sites:
                phos_span[size].append(TrackElement(site.position - shift, size))

        for size in phos_span.keys():
            self.trim_ends(phos_span[size])

        return [
            Track('phos_span_' + str(size), phos_span[size], inline=True)
            for size in spans
        ]

    def trim_ends(self, elements):
        if not elements:
            return
        # do not exceed 0 on the beginning or stop codon at the end
        elements[0].start = max(elements[0].start, 0)
        last_start = elements[-1].start
        elements[-1].length = min(elements[-1].length + last_start, self.length) - last_start


class MutationsTrack(Track):

    def __init__(self, raw_mutations):

        tracks = []
        for mutations in self.group_mutations(raw_mutations):
            tracks.append([])
            for mutation in mutations.values():
                element = TrackElement(mutation.position, 1, mutation.mut_residue)
                tracks[-1].append(element)

        subtracks = [Track('', muts) for muts in tracks[1:]]

        super().__init__('mutations', tracks[0], subtracks)

    def group_mutations(self, mutations):

        grouped = [{}]
        for mutation in mutations:
            depth = 0
            pos = mutation.position
            try:
                while pos in grouped[depth]:
                    if grouped[depth][pos].mut_residue == mutation.mut_residue:
                        # TODO: increace frequency count
                        break
                    depth += 1
            except IndexError:
                grouped.append({})
            grouped[depth][pos] = mutation

        # TODO: sort by occurence count
        return grouped


class PositionTrack(Track):

    def __init__(self, length, step):
        element_size = len(str(length))
        if step < element_size:
            raise Exception('PositionTrack elements will overlap with current step')
        elements = [TrackElement(i, element_size, i) for i in range(0, length, step)]
        super().__init__('position', elements)
