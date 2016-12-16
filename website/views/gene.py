from flask import render_template as template
from flask import jsonify
from flask import request
from flask_classful import FlaskView
from flask_classful import route
from models import Protein
from models import Mutation
from models import Gene
from models import Site
from sqlalchemy import func
from sqlalchemy import distinct
from sqlalchemy import case
from sqlalchemy import literal_column
from database import db
from website.helpers.views import AjaxTableView
from website.helpers.filters import FilterManager
from website.helpers.filters import Filter
from website.helpers.widgets import FilterWidget
from website.views._global_filters import sources_to_sa_filter


class GeneViewFilters(FilterManager):

    def __init__(self, **kwargs):
        filters = [
            Filter(
                Mutation, 'sources', comparators=['in'],
                choices=list(Mutation.source_fields.keys()),
                default=None, nullable=True,
                as_sqlalchemy=sources_to_sa_filter
            ),
            Filter(
                Site, 'type', comparators=['in'],
                choices=[
                    'phosphorylation', 'acetylation',
                    'ubiquitination', 'methylation'
                ],
                as_sqlalchemy=True
            )
        ]
        super().__init__(filters)
        self.update_from_request(request)


def make_widgets(filter_manager):
    return {
        'dataset': FilterWidget(
            'Mutation dataset', 'select',
            filter=filter_manager.filters['Mutation.sources'],
            labels=[
                'Cancer (TCGA)',
                'Clinical (ClinVar)',
                'Population (ESP 6500)',
                'Population (1000 Genomes)'
            ],
            disabled_label='All datasets'
        ),
        'ptm_type': FilterWidget(
            'Type of PTM site', 'select',
            filter=filter_manager.filters['Site.type'],
            disabled_label='all sites'
        )
    }


def ajax_query():
    query = (
        db.session.query(
            Gene.name,
            func.count(distinct(Mutation.id)).label('muts_cnt'),
            func.count(distinct(case(
                [
                    (
                        (
                            Site.position.between(
                                Mutation.position - 7,
                                Mutation.position + 7
                            )
                        ),
                        Mutation.id
                    )
                ],
                else_=literal_column('NULL')
            ))).label('ptm_muts_cnt'),
            func.count(distinct(Site.id)).label('ptm_sites_cnt')
        )
        .select_from(Gene)
        .join(Protein, Protein.id == Gene.preferred_isoform_id)
        .outerjoin(Site, Site.protein_id == Protein.id)
        .outerjoin(Mutation, Mutation.protein_id == Protein.id)
        .group_by(Gene.id)
    )
    return query


class GeneView(FlaskView):

    def show(self, gene_name):
        gene = Gene.query.filter_by(name=gene_name).one()
        return template('gene/show.html', gene=gene)

    def before_request(self, name, *args, **kwargs):
        filter_manager = GeneViewFilters()
        endpoint = self.build_route_name(name)

        return filter_manager.reformat_request_url(
            request, endpoint, *args, **kwargs
        )

    def isoforms(self, gene_name):
        gene = Gene.query.filter_by(name=gene_name).one()
        return jsonify({
            'preferred': gene.preferred_isoform.to_json(),
            'alternative': [
                isoform.to_json()
                for isoform in gene.alternative_isoforms
            ]
        })

    def browse(self):
        filter_manager = GeneViewFilters()
        widgets = make_widgets(filter_manager)
        return template('gene/browse.html', widgets=widgets)

    browse_data = route('browse_data')(
        AjaxTableView.from_query(
            query=ajax_query(),
            results_mapper=lambda row: row._asdict(),
            filters_class=GeneViewFilters,
            search_filter=lambda q: Gene.name.like(q + '%'),
            count_query=(
                db.session.query(
                    Gene.id
                )
                .select_from(Gene)
                .join(Protein, Protein.id == Gene.preferred_isoform_id)
                .group_by(Gene.name)
            ),
            sort='name'
        )
    )
