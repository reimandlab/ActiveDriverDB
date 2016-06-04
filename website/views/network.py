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

        neighbours = protein.kinases

        return template('network.html', protein=protein, neighbours=neighbours,
                        filters=filters)
