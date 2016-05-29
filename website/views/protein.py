import json
from flask import request
from flask import render_template as template
# from flask import flash, url_for, redirect, abort
from flask_classful import FlaskView
# from flask_classful import route
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
from website.models import Mutation
from website.models import db
from sqlalchemy import func
from sqlalchemy.sql import label


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
        active_filters = FilterSet.from_request(request)

        protein = Protein.query.filter_by(name=name).first_or_404()

        disorder = [
            TrackElement(*region) for region in protein.disorder_regions
        ]
        mutations = filter(active_filters.test, protein.mutations)

        tracks = [
            PositionTrack(protein.length, 25),
            SequenceTrack(protein),
            MutationsTrack(mutations),
            Track('disorder', disorder)
        ]

        filters = Filters(active_filters, self.allowed_filters)

        mutations = db.session.query(
            Mutation,
            label('count', func.count(Mutation.position))).\
            join(Protein).filter_by(id=protein.id).\
            group_by(Mutation.position, Mutation.mut_residue)

        return template('protein.html', protein=protein, tracks=tracks,
                        filters=filters, mutations_with_cnt=mutations)

    def mutations(self, name):
        """List of mutations suitable for needleplot library"""
        protein = Protein.query.filter_by(name=name).first_or_404()
        filters = request.args.get('filters', '')
        filters = FilterSet.from_string(filters)

        response = []

        for key, mutations in protein.mutations_grouped.items():

            mutations = list(filter(filters.test, mutations))

            if len(mutations):
                position, mut_residue, cancer_type = key
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
