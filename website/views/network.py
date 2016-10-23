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

    def _make_filters(self):
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
        return filters, filter_manager

    def _make_widgets(self, filters, filter_manager):
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

        return filter_widgets, option_widgets

    def before_request(self, name, *args, **kwargs):
        pass

    def index(self):
        """Show SearchView as deafault page"""
        return redirect(url_for('SearchView:index', target='proteins'))

    def show(self, refseq):
        """Show a protein network visualisation"""

        filters, filter_manager = self._make_filters()
        filter_widgets, option_widgets = self._make_widgets(filters, filter_manager)
        filter_manager.update_from_request(request)

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()
        data = self._prepare_network_repr(protein, filter_manager)

        return template(
            'network.html', protein=protein, data=data,
            filters=filter_manager,
            option_widgets=option_widgets,
            filter_widgets=filter_widgets
        )

    def _prepare_network_repr(self, protein, filter_manager, include_kinases_from_groups=False):

        protein_mutations = filter_manager.apply(protein.mutations)

        sites = [
            site for site in filter_manager.apply(protein.sites)
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

        source = filter_manager.get_value('Mutation.sources')

        kinases_counts = dict()
        for kinase in kinases:
            if kinase.protein:
                from models import Mutation
                from sqlalchemy import and_
                mutations = Mutation.query.filter(
                    and_(
                        Mutation.protein == kinase.protein,
                        source in Mutation.sources
                    )
                ).all()
                count = len(filter_manager.apply(mutations))
                # assert count == len(filter_manager.apply(kinase.mutations))
                if count > 0:
                    kinases_counts[kinase] = count

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

        def get_site_mutations(site):
            return [
                mutation
                for mutation in protein_mutations
                if abs(mutation.position - site.position) < 7
            ]

        def most_significant_impact(impacts):
            desc = ['direct', 'network-rewiring', 'proximal', 'distal', 'none']
            for impact in desc:
                if impact in impacts:
                    return impact
            return desc[-1]

        def prepare_site(site):
            site_mutations = get_site_mutations(site)
            return {
                'position': site.position,
                'residue': site.residue,
                'kinases': [kinase.name for kinase in site.kinases],
                'kinase_groups': [
                    group.name for group in site.kinase_groups
                ],
                'kinases_count': len(site.kinases),
                'nearby_sequence': get_nearby_sequence(site, protein),
                'mutations_count': len(site_mutations),
                'mimp_losses': [
                    mimp.pwm
                    for mutation in site_mutations
                    for mimp in mutation.meta_MIMP
                    if not mimp.effect
                ],
                'impact': most_significant_impact(set(
                    mutation.impact_on_specific_ptm(site)
                    for mutation in site_mutations
                ))
            }

        data = {
            'kinases': kinase_reprs,
            'protein': {
                'name': protein.gene.name,
                'is_preferred': protein.is_preferred_isoform,
                'refseq': protein.refseq,
                'mutations_count': len(protein_mutations),
                'kinases': protein_kinases_names
            },
            'sites': [
                prepare_site(site)
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
