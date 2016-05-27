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
from website.helpers.filters import Filters
from website.helpers.filters import Filter


class ProteinView(FlaskView):
    """Single protein view: includes needleplot and sequence"""

    allowed_filters = FilterSet([
        Filter('is_ptm', 'eq', None, 'binary', 'PTM mutations')
    ])

    def index(self):
        """Show SearchView as deafault page"""
        return SearchView().index(target='protein')

    def show(self, name):
        """Show a protein by:

        + needleplot
        + tracks (seuqence + data tracks)
        """
        filters_str = request.args.get('filters', '')
        active_filters = FilterSet.from_string(filters_str)

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

        mutations = filter(active_filters.test, protein.mutations)

        tracks = [
            PositionTrack(protein.length, 25),
            SequenceTrack(protein),
            MutationsTrack(mutations),
            Track('disorder', disorder)
        ]

        from copy import deepcopy
        available_filters = deepcopy(self.allowed_filters)
        active_filters.remove_unused()
        print('x',[x for x in active_filters.filters])

        for passed_filter in active_filters:
            for allowed_filter in available_filters:
                if allowed_filter.property == passed_filter.property:
                    passed_filter.name = allowed_filter.name
                    passed_filter.type = allowed_filter.type
                    available_filters.filters.remove(allowed_filter)
                    break
            else:
                active_filters.filters.remove(passed_filter)
                raise Exception('Filter {0} not allowed'.format(passed_filter))

        filters = Filters(active_filters, FilterSet(available_filters))

        return template('protein.html', protein=protein, tracks=tracks, filters=filters)

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
