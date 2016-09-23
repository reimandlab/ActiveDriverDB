import json
from flask import request
from flask import redirect
from flask import url_for
from flask import render_template as template
from flask_classful import FlaskView
from models import Protein
from models import Site
from website.helpers.filters import Filter
from website.helpers.filters import FilterManager
from website.helpers.widgets import FilterWidget


def get_nearby_sequence(site, protein, dst=3):
    left = site.position - dst - 1
    right = site.position + dst
    return (
        '-' * -min(0, left) +
        protein.sequence[max(0, left):min(right, protein.length)] +
        '-' * (max(protein.length, left) - protein.length)
    )


class Target:
    __name__ = 'JavaScript'


class NetworkView(FlaskView):
    """View for local network of proteins"""

    # TODO: use filter manager only for true filters,
    # make an "option manager" for options.
    filter_manager = FilterManager(
        [
            Filter(
                Target(), 'show_sites',
                comparators=['eq'], default=True
            ),
            Filter(
                Target(), 'clone_by_site',
                comparators=['eq'], default=True
            ),
            Filter(
                Site, 'type', comparators=['in'],
                choices=[
                    'phosphorylation', 'acetylation',
                    'ubiquitination', 'methylation'
                ],
            ),
        ]
    )

    filter_widgets = [
        FilterWidget(
            'Site type', 'select',
            filter=filter_manager.filters['Site.type']
        )
    ]

    option_widgets = [
        FilterWidget(
            'Show sites', 'binary',
            filter=filter_manager.filters['JavaScript.show_sites']
        ),
        FilterWidget(
            'Clone kinases by site', 'binary',
            filter=filter_manager.filters['JavaScript.clone_by_site']
        ),
    ]

    def before_request(self, name, *args, **kwargs):
        self.filter_manager.reset()
        self.filter_manager.update_from_request(request)

    def index(self):
        """Show SearchView as deafault page"""
        return redirect(url_for('SearchView:index', target='proteins'))

    def show(self, refseq):
        """Show a protein network visualisation"""

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()
        data = self._prepare_network_repr(protein)
        return template(
            'network.html', protein=protein, data=data,
            filters=self.filter_manager,
            option_widgets=self.option_widgets,
            filter_widgets=self.filter_widgets
        )

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
                        'refseq': kinase.protein.refseq,
                        'mutations_count': kinase.protein.mutations.count()
                    } if kinase.protein else None
                }
                for kinase in kinases
            ],
            'protein': {
                'name': protein.gene.name,
                'is_preferred': protein.is_preferred_isoform,
                'refseq': protein.refseq,
                'mutations_count': protein.mutations.count(),
                'kinases': protein_kinases_names
            },
            'sites': [
                {
                    'position': site.position,
                    'residue': site.residue,
                    'kinases': [kinase.name for kinase in site.kinases],
                    'kinases_count': len(site.kinases),
                    'nearby_sequence': get_nearby_sequence(site, protein)
                }
                # TODO: remove unused kinases
                for site in self.filter_manager.apply(protein.sites)
                if site.kinases
            ],
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
