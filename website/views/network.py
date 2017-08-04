from collections import namedtuple, defaultdict

from flask import request, abort, Response, json
from flask import redirect
from flask import url_for
from flask import jsonify
from flask import render_template as template
from flask_classful import FlaskView

from models import Protein, Mutation, Drug, Gene
from helpers.filters import Filter
from helpers.filters import FilterManager
from helpers.widgets import FilterWidget
from ._global_filters import common_filters, filters_data_view
from ._global_filters import create_widgets


class Target:
    __name__ = 'JavaScript'


def js_toggle(name, default=True):
    return Filter(
        Target(), name,
        comparators=['eq'], default=default
    )


class NetworkViewFilters(FilterManager):

    def __init__(self, protein, **kwargs):

        filters = common_filters(protein, **kwargs)

        # TODO: use filter manager only for true filters, make an "option manager" for options?
        filters += [
            js_toggle('show_sites'),
            js_toggle('clone_by_site'),
            js_toggle('collide_drugs'),
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


class NetworkRepresentation:

    def __init__(self, protein, filter_manager, include_kinases_from_groups=False):
        self.protein = protein
        self.filter_manager = filter_manager
        self.include_kinases_from_groups = include_kinases_from_groups

        from models import Mutation
        from sqlalchemy import and_

        # TODO: all of this could be fetched in a single query
        self.protein_mutations = filter_manager.query_all(
            Mutation,
            lambda q: and_(q, Mutation.protein == protein)
        )

        sites, kinases = self.get_sites_and_kinases()

        kinases_counts = dict()
        for kinase in kinases:
            if kinase.protein:

                count = filter_manager.query_count(
                    Mutation,
                    lambda q: and_(q, Mutation.protein == kinase.protein)
                )

                # related discussion: #72
                kinases_counts[kinase] = count

                # KINASES NOT MAPPED TO PROTEINS ARE NOT SHOWN

        # kinases = set(kinases_counts.keys())

        sites = [
            site
            for site in sites
            if site.kinases or site.kinase_groups
        ]

        protein_kinases_names = [kinase.name for kinase in kinases]
        kinase_gene_ids = [kinase.protein.gene_id for kinase in kinases if kinase.protein]

        drugs = filter_manager.query_all(
            Drug,
            lambda q: and_(
                q,
                Gene.id.in_(kinase_gene_ids)
            ),
            lambda query: query.join(Drug.target_genes)
        )
        drugs_by_kinase = defaultdict(set)
        for drug in drugs:
            for target_gene in drug.target_genes:
                drugs_by_kinase[target_gene].add(drug)

        kinase_reprs = []
        for kinase, count in kinases_counts.items():
            json_repr = kinase.to_json()
            if json_repr['protein']:
                json_repr['protein']['mutations_count'] = count

            json_repr['drugs_targeting_kinase_gene'] = [
                drug.to_json() for drug in drugs_by_kinase[kinase.protein.gene]
            ]
            kinase_reprs.append(json_repr)

        self.muts_by_site = divide_muts_by_sites(self.protein_mutations, sites)

        groups = set()

        for site in sites:
            groups.update(site.kinase_groups)

        data = {
            'kinases': kinase_reprs,
            'protein': {
                'name': protein.gene.name,
                'is_preferred': protein.is_preferred_isoform,
                'refseq': protein.refseq,
                'mutations_count': len(self.protein_mutations),
                'kinases': protein_kinases_names
            },
            'sites': [
                self.prepare_site(site)
                for site in sites
            ],
            'kinase_groups': [
                {
                    'name': group.name,
                    'kinases': list(
                        {
                            kinase.name
                            for kinase in group.kinases
                        }.intersection(protein_kinases_names)
                    ),
                    'total_cnt': len(group.kinases)
                }
                for group in groups
            ]
        }
        self.data = data

    @staticmethod
    def most_significant_impact(impacts):
        desc = ['direct', 'network-rewiring', 'proximal', 'distal', 'none']
        for impact in desc:
            if impact in impacts:
                return impact
        return desc[-1]

    def get_site_kinases(self, site):
        return site.kinases

    def get_site_kinase_groups(self, site):
        return site.kinase_groups

    def prepare_site(self, site):
        site_mutations = self.muts_by_site[site]
        mutations = [
            {
                'ref': mutation.ref,
                'pos': mutation.position,
                'alt': mutation.alt,
                'impact': mutation.impact_on_specific_ptm(site)
            }
            for mutation in site_mutations
        ]

        site_kinases = self.get_site_kinases(site)
        site_kinase_groups = self.get_site_kinase_groups(site)

        return {
            'position': site.position,
            'residue': site.residue,
            'ptm_type': site.type,
            'kinases': [kinase.name for kinase in site_kinases],
            'kinase_groups': [group.name for group in site_kinase_groups],
            'kinases_count': len(site_kinases),
            'sequence': site.sequence,
            'mutations_count': len(site_mutations),
            'mutations': mutations,
            'mimp_losses': [
                mimp.pwm
                for mutation in site_mutations
                for mimp in mutation.meta_MIMP
                if mimp.is_loss
            ],
            'mimp_gains': [
                mimp.pwm
                for mutation in site_mutations
                for mimp in mutation.meta_MIMP
                if mimp.is_gain
            ],
            'impact': self.most_significant_impact(set(
                mutation['impact']
                for mutation in mutations
            ))
        }

    def as_json(self):
        return self.data

    def get_sites_and_kinases(self):
        from models import Site
        from sqlalchemy import and_
        from sqlalchemy import or_
        sites = [
            site
            for site in self.filter_manager.query_all(
                Site,
                lambda q: and_(
                    q,
                    Site.protein == self.protein,
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
                (site.kinase_groups if self.include_kinases_from_groups else [])
            )
        )
        return sites, kinases


def list_without_nones(iterable):
    return list(filter(lambda x: x is not None, iterable))


class PredictedNetworkRepresentation(NetworkRepresentation):

    def get_sites_and_kinases(self):
        mimp_mutations = [m for m in self.protein_mutations if m.meta_MIMP]
        sites = set()
        kinases = set()
        for mimp_mutation in mimp_mutations:
            for mimp in mimp_mutation.meta_MIMP:
                sites.add(mimp.site)
                kinases.add(mimp.kinase)
        return sites, kinases

    def get_site_kinases(self, site):
        site_mutations = self.muts_by_site[site]
        return list_without_nones({
            mimp.kinase
            for mutation in site_mutations
            for mimp in mutation.meta_MIMP
        })

    def get_site_kinase_groups(self, site):
        site_mutations = self.muts_by_site[site]
        return list_without_nones({
            mimp.kinase_group
            for mutation in site_mutations
            for mimp in mutation.meta_MIMP
        })


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
            FilterWidget(
                'Prevent drug overlapping', 'binary',
                filter=filter_manager.filters['JavaScript.collide_drugs']
            ),
        ]

    def before_request(self, name, *args, **kwargs):
        protein = Protein.query.filter_by(refseq=kwargs['refseq']).first_or_404()
        filter_manager = NetworkViewFilters(protein)
        endpoint = self.build_route_name(name)

        return filter_manager.reformat_request_url(
            request, endpoint, *args, **kwargs
        )

    def index(self):
        """Show SearchView as default page"""
        return redirect(url_for('SearchView:default', target='proteins'))

    def show(self, refseq, predicted_interactions=False):
        """Show a protein network visualisation"""

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()

        filter_manager = NetworkViewFilters(protein)
        filters_by_id = filter_manager.filters

        return template(
            'network/show.html', protein=protein,
            filters=filter_manager,
            option_widgets=self._create_option_widgets(filter_manager),
            widgets=create_widgets(protein, filters_by_id),
            mutation_types=Mutation.types,
            predicted_interactions=predicted_interactions
        )

    def predicted(self, refseq):
        return self.show(refseq, predicted_interactions=True)

    def _as_tsv(self, protein, filter_manager):
        header = [
            'target_protein', 'target_protein_refseq',
            'target_site', 'target_site_type',
            'target_site_mutation_impact', 'bound_enzyme',
            'drug_targeting_bound_enzyme'
        ]
        content = ['#' + '\t'.join(header)]

        network = NetworkRepresentation(protein, filter_manager).as_json()

        for site in network['sites']:
            target_site = '%s,%s' % (site['position'], site['residue'])
            protein_and_site = [protein.gene_name, protein.refseq, target_site, site['ptm_type'], site['impact']]

            for kinase_name in site['kinases']:
                try:
                    kinase = list(filter(lambda k: k['name'] == kinase_name, network['kinases']))[0]
                except IndexError:
                    continue
                drugs = kinase['drugs_targeting_kinase_gene']
                drugs = ','.join([drug['name'] for drug in drugs]) or ''
                row = protein_and_site + [kinase_name, drugs]
                content.append('\t'.join(row))

            for kinase_group in site['kinase_groups']:
                row = protein_and_site + [kinase_group]
                content.append('\t'.join(row))

        return '\n'.join(content)

    def download(self, refseq, format):

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()
        filter_manager = NetworkViewFilters(protein)

        Formatter = namedtuple('Formatter', 'get_content mime_type extension')

        formatters = {
            'json': Formatter(
                lambda: json.dumps(NetworkRepresentation(protein, filter_manager).as_json()),
                'text/json',
                'json'
            ),
            'tsv': Formatter(
                lambda: self._as_tsv(protein, filter_manager),
                'text/tsv',
                'tsv'
            )
        }

        if format not in formatters:
            raise abort(404)

        formatter = formatters[format]

        name = refseq + '-' + filter_manager.url_string(expanded=True)

        filename = '%s.%s' % (name, formatter.extension)

        return Response(
            formatter.get_content(),
            mimetype=formatter.mime_type,
            headers={'Content-disposition': 'attachment; filename="%s"' % filename}
        )

    def predicted_representation(self, refseq):
        return self.representation(refseq, include_mimp_gain_kinases=True)

    def representation(self, refseq, include_mimp_gain_kinases=False):

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()

        filter_manager = NetworkViewFilters(protein)

        if include_mimp_gain_kinases:
            representation = PredictedNetworkRepresentation(protein, filter_manager)
        else:
            representation = NetworkRepresentation(protein, filter_manager)

        response = {
            'representation': {
                'network': representation.as_json(),
                'clone_by_site': filter_manager.get_value('JavaScript.clone_by_site'),
                'show_sites': filter_manager.get_value('JavaScript.show_sites'),
                'collide_drugs': filter_manager.get_value('JavaScript.collide_drugs'),
            },
            'filters': filters_data_view(protein, filter_manager)
        }

        return jsonify(response)
