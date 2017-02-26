from flask import render_template as template
from flask import jsonify
from flask import request
from flask_classful import FlaskView
from flask_classful import route
from models import Protein
from models import Mutation
from models import Gene
from models import Site
from models import GeneList
from models import GeneListEntry
from sqlalchemy import func
from sqlalchemy import distinct
from sqlalchemy import case
from sqlalchemy import literal_column
from database import db
from helpers.views import AjaxTableView
from helpers.filters import FilterManager
from helpers.filters import Filter
from helpers.widgets import FilterWidget
from ._global_filters import sources_to_sa_filter

from sqlalchemy import and_
import sqlalchemy


def select_filters(filters, models):
    """Selects filters which are applicable to at least one of given models."""
    selected = set()
    tables = [model.__table__ for model in models]

    table_containing_types = [
        sqlalchemy.sql.schema.Column,
        sqlalchemy.sql.annotation.AnnotatedColumn
    ]

    for filter_ in filters:
        stack = list(filter_.get_children())
        for entity in stack:
            if type(entity) in table_containing_types:
                if entity.table in tables:
                    selected.add(filter_)
            if isinstance(entity, sqlalchemy.sql.selectable.Selectable):
                stack.extend(entity.get_children())
    return selected


def prepare_subqueries(sql_filters):
    """Return three sub-queries suitable for use in protein queries which are:
        - mutations count (muts_cnt),
        - PTM mutations count (ptm_muts_cnt),
        - sites count (ptm_sites_cnt)

    Returned sub-queries are labelled as shown in parentheses above.
    """
    muts = (
        db.session.query(func.count(Mutation.id))
        .filter(Mutation.protein_id == Protein.id)
        .filter(and_(*select_filters(sql_filters, [Mutation])))
    ).label('muts_cnt')

    if sql_filters:
        ptm_muts = (
            db.session.query(
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
                )))
            )
            .filter(and_(
                Mutation.protein_id == Protein.id,
                Site.protein_id == Protein.id,
                Mutation.precomputed_is_ptm
            ))
            .join(Site, Site.protein_id == Mutation.protein_id)
            .filter(and_(*select_filters(sql_filters, [Site, Mutation])))
        )
    else:
        ptm_muts = (
            db.session.query(func.count(Mutation.id))
            .filter(and_(
                Mutation.protein_id == Protein.id,
                Mutation.precomputed_is_ptm
            ))
            .filter(and_(*select_filters(sql_filters, [Mutation])))
        )
    ptm_muts = ptm_muts.label('ptm_muts_cnt')

    sites = (
        db.session.query(func.count(Site.id))
            .filter(
            Site.protein_id == Protein.id,
            )
            .filter(and_(*select_filters(sql_filters, [Site])))
    ).label('ptm_sites_cnt')

    return muts, ptm_muts, sites


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
                choices=Site.types,
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


def ajax_query(sql_filters):

    muts, ptm_muts, sites = prepare_subqueries(sql_filters)

    query = (
        db.session.query(
            Gene.name,
            muts,
            ptm_muts,
            sites
        )
        .select_from(Gene)
        .join(Protein, Protein.id == Gene.preferred_isoform_id)
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

    def list(self, list_name):
        filter_manager = GeneViewFilters()
        widgets = make_widgets(filter_manager)
        return template(
            'gene/list.html', list_name=list_name,
            widgets=widgets, filter_manager=filter_manager
        )

    def lists(self):
        lists = GeneList.query.all()
        return template('gene/lists.html', lists=lists)

    def list_data(self, list_name):
        gene_list = GeneList.query.filter_by(name=list_name).first_or_404()

        def query_constructor(sql_filters):
            # TODO: create "PurportedMutation" for MIMP data, skip MIMP mutations somehow.

            muts, ptm_muts, sites = prepare_subqueries(sql_filters)

            return (
                db.session.query(
                    Gene.name,
                    muts,
                    ptm_muts,
                    sites,
                    GeneListEntry.fdr,
                    GeneListEntry.p
                )
                .select_from(GeneListEntry)
                .filter(GeneListEntry.gene_list_id == gene_list.id)
                .join(Gene, Gene.id == GeneListEntry.gene_id)
                .join(Protein, Protein.id == Gene.preferred_isoform_id)
                .group_by(Gene.id)
            )

        ajax_view = AjaxTableView.from_query(
            query_constructor=query_constructor,
            results_mapper=lambda row: row._asdict(),
            filters_class=GeneViewFilters,
            search_filter=lambda q: Gene.name.like(q + '%'),
            count_query=(
                db.session.query(
                    GeneListEntry.id
                )
                .select_from(GeneListEntry)
                .join(Gene, GeneListEntry.gene_id == Gene.id)
                .join(Protein, Protein.id == Gene.preferred_isoform_id)
                .filter(GeneListEntry.gene_list_id == gene_list.id)
            ),
            sort='fdr'
        )
        return ajax_view(self)

    def browse(self):
        filter_manager = GeneViewFilters()
        widgets = make_widgets(filter_manager)
        return template('gene/browse.html', widgets=widgets)

    browse_data = route('browse_data')(
        AjaxTableView.from_query(
            query_constructor=ajax_query,
            results_mapper=lambda row: row._asdict(),
            filters_class=GeneViewFilters,
            search_filter=lambda q: Gene.name.like(q + '%'),
            count_query=(
                db.session.query(Gene.id)
                .select_from(Gene)
                .join(Protein, Protein.id == Gene.preferred_isoform_id)
                .group_by(Gene.id)
            ),
            sort='name'
        )
    )
