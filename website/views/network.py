from operator import itemgetter
from flask import request
from flask import jsonify
from flask import render_template as template
from flask_classful import FlaskView
from website.models import Protein
from website.views import SearchView
from website.helpers.filters import FilterSet
from website.helpers.filters import Filters
from website.helpers.filters import Filter
from website.models import Mutation
from website.database import db
from sqlalchemy import func
from sqlalchemy.sql import label


class NetworkView(FlaskView):
    """View for local network of proteins"""

    allowed_filters = FilterSet([
        Filter('is_ptm', 'eq', None, 'binary', 'PTM mutations')
    ])

    def index(self):
        """Show SearchView as deafault page"""
        return SearchView().index(target='network')

    def show(self, name):
        """Show a protein by"""
        active_filters = FilterSet.from_request(request)
        filters = Filters(active_filters, self.allowed_filters)

        protein = Protein.query.filter_by(name=name).first_or_404()
        data = self._prepare_network_repr(protein)

        return template('network.html', protein=protein, data=data,
                        filters=filters)

    def _prepare_network_repr(self, protein):
        import json

        kinases_from_groups = sum(
            [group.kinases for group in protein.kinase_groups],
            []
        )

        data = {
            'kinases': [
                {
                    'name': kinase.name,
                    'protein': {
                        'mutations_count': kinase.protein.mutations.count()
                    } if kinase.protein else None
                }
                for kinase in set(protein.kinases).union(kinases_from_groups)
            ],
            'protein': {
                'name': protein.name,
                'mutations_count': protein.mutations.count()
            },
            'kinase_groups': [
                {
                    'name': group.name,
                    'kinases': [
                        kinase.name
                        for kinase in group.kinases
                    ]
                }
                for group in protein.kinase_groups
            ]
        }
        return json.dumps(data)

    def kinases(self, name):

        protein = Protein.query.filter_by(name=name).first_or_404()
        data = self._prepare_network_repr(protein)

        return data
