class Track(object):

    def __init__(self, name, elements, subtracks='', inline=False):
        self.name = name
        self.elements = elements
        self.subtracks = subtracks
        self.inline = inline


class TrackElement(object):

    def __init__(self, start, end, name=''):
        self.start = start
        self.end = end
        self.name = name


class SequenceTrack(Track):

    def __init__(self, protein):

        # mutatated_residues = [TrackElement(mutation.position, 1) for mutation in protein.mutations]
        phosporylations = [TrackElement(site.position - 3, 7) for site in protein.sites]
        phosporylations_pinpointed = [TrackElement(site.position - 1, 3) for site in protein.sites]

        subtracks = [
            Track('phosphorylation', phosporylations, inline=True),
            Track('phosphorylation_pinpointed', phosporylations_pinpointed, inline=True),
        ]

        super().__init__('sequence', protein.sequence, subtracks)


class MutationsTrack(Track):

    def __init__(self, mutations):

        mutations = self.group_mutations(mutations)
        tracks = [[TrackElement(m.position, 1, m.mut_residue) for m in ms.values()] for ms in mutations]

        subtracks = [Track('&nbsp;', muts) for muts in tracks[1:]]

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
