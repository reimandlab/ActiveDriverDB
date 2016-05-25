import json
from flask import request, flash, url_for, redirect, abort, render_template as template
from flask_classful import FlaskView, route
from website.models import Protein
from website.views import SearchView
from website.helpers.tracks import Track
from website.helpers.tracks import TrackElement
from website.helpers.tracks import PositionTrack
from website.helpers.tracks import SequenceTrack
from website.helpers.tracks import MutationsTrack
from website.helpers.filters import FilterSet


class ProteinView(FlaskView):
    """Single protein view: includes needleplot and sequence"""

    def index(self):
        """Show SearchView as deafault page """
        return SearchView().index(target='protein')

    def show(self, name):
        """Show a protein by:

        + needleplot
        + tracks (seuqence + data tracks)
        """
        filters_str = request.args.get('filters', '')
        filters = FilterSet.from_string(filters_str)

        protein = Protein.query.filter_by(name=name).first_or_404()

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

        disorder = [TrackElement(*region) for region in disorder_regions]

        mutations = filter(filters.test, protein.mutations)

        tracks = [
            PositionTrack(protein.length, 25),
            SequenceTrack(protein),
            MutationsTrack(mutations),
            Track('disorder', disorder)
        ]
        return template('protein.html', protein=protein, tracks=tracks, filters=filters_str)

    def mutations(self, name):
        """List of mutations suitable for needleplot library"""
        protein = Protein.query.filter_by(name=name).first_or_404()
        filters = request.args.get('filters', '')
        filters = FilterSet.from_string(filters)

        response = []

        for key, mutations in protein.mutations_grouped.items():

            mutations = list(filter(filters.test, mutations))

            if len(mutations):
                position, cancer_type = key
                needle = {
                    'coord': str(position),
                    'value': len(mutations),
                    'category': cancer_type
                }
                response += [needle]

        return json.dumps(response)

    def sites(self, name):
        """List of sites suitable for needleplot library"""

        protein = Protein.query.filter_by(name=name).first_or_404()

        response = [
            {
                'coord': str(site.position - 7) + '-' + str(site.position + 7),
                'name': str(site.position) + 'Ph'
            } for site in protein.sites
        ]

        return json.dumps(response)
