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

        subtracks = self.phosporylation_subtracks()

        super().__init__('sequence', protein.sequence, subtracks)

    def phosporylation_subtracks(self):

        # store in descending order or use z-index
        spans = (7, 3)
        phos_span = {}

        for shift in spans:
            size = 2 * shift + 1

            coords = [
                [site.position - shift, size]
                for site in self.protein.sites
            ]
            self.trim_ends(coords)

            phos_span[shift] = [
                TrackElement(start, length)
                for start, length in coords
            ]

        return [
            Track('phos_span_' + str(shift), phos_span[shift], inline=True)
            for shift in spans
        ]

    def trim_ends(self, elements):
        """Trim coordinates defining TrackElements to fit into the track"""
        # Meaning of indices: [0] = start, [1] = length

        # do not exceed 0 on the beginning
        begin_pos = 0
        while elements[begin_pos][0] < 0:
            elements[begin_pos][0] = 0
            begin_pos += 1

        # and do not exceed sequence length at the end
        final_pos = -1
        while elements[final_pos][1] > self.length - elements[final_pos][0]:
            elements[final_pos][1] = self.length - elements[final_pos][0]
            final_pos -= 1


class MutationsTrack(Track):

    def __init__(self, raw_mutations):

        tracks = []
        for mutations in self.group_mutations(raw_mutations):
            track = [
                TrackElement(mutation.position - 1, 1, mutation.mut_residue)
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
