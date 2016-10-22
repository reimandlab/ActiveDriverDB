import json
from flask import request
from flask import redirect
from flask import url_for
from flask import render_template as template
from flask_classful import FlaskView
from models import Protein
from website.helpers.filters import Filter
from website.helpers.filters import FilterManager
from website.helpers.widgets import FilterWidget
from website.views._global_filters import common_filters
from website.views._global_filters import common_widgets


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

    filters = common_filters()

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
        ] + filters
    )

    filter_widgets = common_widgets(filters)

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

        sites = [
            site for site in self.filter_manager.apply(protein.sites)
            if site.kinases or site.kinase_groups
        ]

        kinases = set(
            kinase
            for site in sites
            for kinase in (
                site.kinases +
                (site.kinase_groups if include_kinases_from_groups else [])
            )
        )

        kinases_counts = {
            kinase: len(self.filter_manager.apply(kinase.mutations))
            for kinase in kinases
        }

        kinases_counts = {
            kinase: count
            for kinase, count in kinases_counts.items()
            if count > 0
        }

        kinases = set(kinases_counts.keys())

        sites = [
            site
            for site in sites
            if kinases.intersection(site.kinases)
        ]

        protein_kinases_names = [kinase.name for kinase in protein.kinases]

        kinase_reprs = []
        for kinase, count in kinases_counts.items():
            json_repr = kinase.to_json()
            if json_repr['protein']:
                json_repr['protein']['mutations_count'] = count
            kinase_reprs.append(json_repr)

        def site_mutations(site):
            return self.filter_manager.apply([
                mutation
                for mutation in protein.mutations
                if abs(mutation.position - site.position) < 7
            ])

        data = {
            'kinases': kinase_reprs,
            'protein': {
                'name': protein.gene.name,
                'is_preferred': protein.is_preferred_isoform,
                'refseq': protein.refseq,
                'mutations_count': len(
                    self.filter_manager.apply(protein.mutations)
                ),
                'kinases': protein_kinases_names
            },
            'sites': [
                {
                    'position': site.position,
                    'residue': site.residue,
                    'kinases': [kinase.name for kinase in site.kinases],
                    'kinase_groups': [
                        group.name for group in site.kinase_groups
                    ],
                    'kinases_count': len(site.kinases),
                    'nearby_sequence': get_nearby_sequence(site, protein),
                    'mutations_count': len(site_mutations(site)),
                    'mimp_losses': [
                        mimp.pwm
                        for mutation in site_mutations(site)
                        for mimp in mutation.meta_MIMP
                        if not mimp.effect
                    ]
                }
                for site in sites
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
                for site in sites
                for group in site.kinase_groups
            ]
        }
        return json.dumps(data)

    def kinases(self, refseq):

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()
        data = self._prepare_network_repr(protein)

        return data
