from flask import request, flash, url_for, redirect, abort, render_template as template
from flask_classful import FlaskView, route
from app import app
import json

from models import Protein


@app.route('/')
def index():
    return template('index.html')


class SearchView(FlaskView):

    categories = {
        'protein': Protein
    }

    def index(self, target):
        return template('search.html', target=target)

    def autocomplete(self, target):
        query = request.args.get('q') or ''

        response = []

        if query:
            qrm = self.categories[target]
            name_filter = qrm.name.like(query + '%')
            entries = qrm.query.filter(name_filter).all()
            response = [{'value': entry.name} for entry in entries]

        return json.dumps(response)


SearchView.register(app)


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


class ProteinView(FlaskView):

    def index(self):
        return SearchView().index(target='protein')

    def show(self, name):
        protein = Protein.query.filter_by(name=name).first_or_404()

        # mutatated_residues = [TrackElement(mutation.position, 1) for mutation in protein.mutations]
        phosporylations = [TrackElement(site.position - 3, 7) for site in protein.sites]
        phosporylations_pinpointed = [TrackElement(site.position - 1, 3) for site in protein.sites]

        disorder_regions = []
        inside_region = False

        for i in range(len(protein.disorder_map)):
            residue = int(protein.disorder_map[i])
            if inside_region:
                if not residue:
                    inside_region = False
                    disorder_regions[-1][1] = i - disorder_regions[-1][0]
            else:
                if residue:
                    disorder_regions += [[i, 1]]
                    inside_region = True

        diseases = [TrackElement(*region) for region in disorder_regions]

        mutations = [{}]
        for mutation in protein.mutations:
            depth = 0
            try:
                while mutation.position in mutations[depth] and mutations[depth][mutation.position].mut_residue != mutation.mut_residue:
                    depth += 1
            except IndexError:
                mutations.append({})
            mutations[depth][mutation.position] = mutation

        # TODO: sort by occurence count

        mutation_tracks = [[TrackElement(m.position, 1, m.mut_residue) for m in ms.values()] for ms in mutations]

        tracks = [
            Track('position', [TrackElement(i, 5, i) for i in range(0, len(protein.sequence), 25)]),
            Track(
                'sequence',
                protein.sequence,
                subtracks=[
                    Track('phosphorylation', phosporylations, inline=True),
                    Track('phosphorylation_pinpointed', phosporylations_pinpointed, inline=True),
                ]),
            Track(
                'mutations',
                mutation_tracks[0],
                subtracks=[Track('+', muts) for muts in mutation_tracks[1:]]
                ),
            Track('diseases', diseases)
        ]
        return template('protein.html', protein=protein, tracks=tracks)

    def mutations(self, name):

        protein = Protein.query.filter_by(name=name).first_or_404()

        response = []

        for key, mutations in protein.mutations_grouped.items():
            position, cancer_type = key
            needle = {
                'coord': str(position),
                'value': len(mutations),
                'category': cancer_type
            }
            response += [needle]

        return json.dumps(response)

    def sites(self, name):

        protein = Protein.query.filter_by(name=name).first_or_404()

        response = [
            {
                'coord': str(site.position - 7) + '-' + str(site.position + 7),
                'name': str(site.position) + 'Ph'
            } for site in protein.sites
        ]

        return json.dumps(response)


ProteinView.register(app)
