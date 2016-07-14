import json
from flask import request
from flask import redirect
from flask import url_for
from flask import render_template as template
from flask_classful import FlaskView
from website.models import Protein
from website.helpers.filters import FilterSet
from website.helpers.filters import Filters
from website.helpers.filters import Filter


class NetworkView(FlaskView):
    """View for local network of proteins"""

    allowed_filters = FilterSet([
        Filter('is_ptm', 'eq', None, 'binary', 'PTM mutations')
    ])

    def index(self):
        """Show SearchView as deafault page"""
        return redirect(url_for('SearchView:index', target='proteins'))

    def show(self, refseq):
        """Show a protein by"""
        active_filters = FilterSet.from_request(request)
        filters = Filters(active_filters, self.allowed_filters)

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()
        data = self._prepare_network_repr(protein)

        return template('network.html', protein=protein, data=data,
                        filters=filters)

    def _prepare_network_repr(self, protein, include_kinases_from_groups=False):

        kinases = set(protein.kinases)

        if include_kinases_from_groups:
            kinases_from_groups = sum(
                [group.kinases for group in protein.kinase_groups],
                []
            )
            kinases.union(kinases_from_groups)

        protein_kinases_names = [kinase.name for kinase in protein.kinases]

        data = {
            'kinases': [
                {
                    'name': kinase.name,
                    'protein': {
                        'mutations_count': kinase.protein.mutations.count()
                    } if kinase.protein else None
                }
                for kinase in kinases
            ],
            'protein': {
                'name': protein.refseq,
                'mutations_count': protein.mutations.count(),
                'kinases': protein_kinases_names
            },
            'kinase_groups': [
                {
                    'name': group.name,
                    'kinases': list({
                        kinase.name
                        for kinase in group.kinases
                    }.intersection(protein_kinases_names)),
                    'total_cnt': len(group.kinases)
                }
                for group in protein.kinase_groups
            ]
        }
        return json.dumps(data)

    def kinases(self, refseq):

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()
        data = self._prepare_network_repr(protein)

        return data
