from flask import request
from flask import redirect
from flask import url_for
from flask import jsonify
from flask import render_template as template
from flask_classful import FlaskView
from models import Protein
from helpers.filters import Filter
from helpers.filters import FilterManager
from helpers.widgets import FilterWidget
from ._global_filters import common_filters
from ._global_filters import create_widgets


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


class NetworkViewFilters(FilterManager):

    def __init__(self, **kwargs):

        filters = common_filters(**kwargs)

        # TODO: use filter manager only for true filters,
        # make an "option manager" for options.
        filters += [
            Filter(
                Target(), 'show_sites',
                comparators=['eq'], default=True
            ),
            Filter(
                Target(), 'clone_by_site',
                comparators=['eq'], default=True
            )
        ]

        super().__init__(filters)
        self.update_from_request(request)


def divide_muts_by_sites(mutations, sites):
    from collections import defaultdict
    muts_by_site = defaultdict(list)

    if not (sites and mutations):
        return muts_by_site

    sites.sort(key=lambda site: site.position)
    mutations.sort(key=lambda mutation: mutation.position)

    m = 0
    for site in sites:
        l = site.position - 7
        p = site.position + 7
        while mutations[m].position < l:
            m += 1
            if m == len(mutations):
                return muts_by_site
        ms = m
        while mutations[ms].position <= p:
            muts_by_site[site].append(mutations[ms])
            ms += 1
            if ms == len(mutations):
                break
    return muts_by_site


class NetworkView(FlaskView):
    """View for local network of proteins"""

    def _create_option_widgets(self, filter_manager):

        return [
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
        filter_manager = NetworkViewFilters()
        endpoint = self.build_route_name(name)

        return filter_manager.reformat_request_url(
            request, endpoint, *args, **kwargs
        )

    def index(self):
        """Show SearchView as default page"""
        return redirect(url_for('SearchView:default', target='proteins'))

    def show(self, refseq):
        """Show a protein network visualisation"""

        filter_manager = NetworkViewFilters()
        filters_by_id = filter_manager.filters

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()

        return template(
            'network/show.html', protein=protein,
            filters=filter_manager,
            option_widgets=self._create_option_widgets(filter_manager),
            widgets=create_widgets(filters_by_id),
        )

    def _prepare_network_repr(self, protein, filter_manager, include_kinases_from_groups=False):
        from models import Mutation, Site
        from sqlalchemy import and_
        from sqlalchemy import or_

        protein_mutations = filter_manager.query_all(
            Mutation,
            lambda q: and_(q, Mutation.protein == protein)
        )

        sites = [
            site
            for site in filter_manager.query_all(
                Site,
                lambda q: and_(
                    q,
                    Site.protein == protein,
                    or_(
                        Site.kinases.any(),
                        Site.kinase_groups.any()
                    )
                )
            )
        ]

        kinases = set(
            kinase
            for site in sites
            for kinase in (
                site.kinases +
                (site.kinase_groups if include_kinases_from_groups else [])
            )
        )

        kinases_counts = dict()
        for kinase in kinases:
            if kinase.protein:

                count = filter_manager.query_count(
                    Mutation,
                    lambda q: and_(q, Mutation.protein == kinase.protein)
                )

                # related discussion: #72
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

        muts_by_site = divide_muts_by_sites(protein_mutations, sites)

        def most_significant_impact(impacts):
            desc = ['direct', 'network-rewiring', 'proximal', 'distal', 'none']
            for impact in desc:
                if impact in impacts:
                    return impact
            return desc[-1]

        def prepare_site(site):
            site_mutations = muts_by_site[site]
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
        return data

    def representation(self, refseq):

        filter_manager = NetworkViewFilters()

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()
        data = self._prepare_network_repr(protein, filter_manager)

        return jsonify(data)
