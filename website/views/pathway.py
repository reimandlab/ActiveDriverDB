from flask import render_template as template, request
from flask import abort
from flask_classful import FlaskView
from flask_classful import route

from database import db
from models import Pathway, GeneList, GeneListEntry, Mutation
from sqlalchemy import or_, func, and_, text
from helpers.views import AjaxTableView


def search_filter(query):
    if query.isnumeric():
        return or_(
            Pathway.gene_ontology.like(query + '%'),
            Pathway.reactome.like(query + '%')
        )
    else:
        return Pathway.description.like('%' + query + '%')


class PathwaysView(FlaskView):

    @route('/gene_ontology/<int:gene_ontology_id>/', endpoint='PathwaysView:show')
    @route('/reactome/<int:reactome_id>/', endpoint='PathwaysView:show')
    def show(self, gene_ontology_id=None, reactome_id=None):

        if gene_ontology_id:
            filter_by = {'gene_ontology': gene_ontology_id}
        elif reactome_id:
            filter_by = {'reactome': reactome_id}
        else:
            raise abort(404)
        pathway = Pathway.query.filter_by(**filter_by).one()

        return template('pathway/show.html', pathway=pathway)

    def index(self):
        lists = GeneList.query.all()
        return template('pathway/index.html', lists=lists)

    def all(self):
        query = request.args.get('query', '')
        return template(
            'pathway/all.html',
            endpoint='all_data',
            endpoint_kwargs={},
            query=query
        )
    #TODO: set eagerload of pathway.genes
    # TODO find other places where such strattegy could speed up

    def with_significant_genes(self, significant_gene_list_name):
        query = request.args.get('query', '')
        gene_list = GeneList.query.filter_by(name=significant_gene_list_name).first_or_404()
        dataset = Mutation.get_source_model(gene_list.mutation_source_name)
        return template(
            'pathway/significant.html',
            gene_list=gene_list,
            dataset=dataset,
            endpoint='significant_data',
            endpoint_kwargs={'gene_list_id': gene_list.id},
            query=query
        )

    all_data = route('all_data')(
        AjaxTableView.from_model(
            Pathway,
            search_filter=search_filter,
            sort='description'
        )
    )

    def significant_data(self, gene_list_id):
        gene_list = GeneList.query.get(gene_list_id)

        def query_constructor(sql_filters):

            significant_genes = (
                db.session.query(
                    GeneListEntry.gene_id
                )
                .select_from(GeneListEntry)
                .filter(GeneListEntry.gene_list_id == gene_list.id)
                .filter(Pathway.association_table.c['gene_id'] == GeneListEntry.gene_id)
            ).label('significant_genes')

            return (
                db.session.query(
                    Pathway,
                    func.count(Pathway.association_table.c['pathway_id']).label('gene_count'),
                    func.count(significant_genes).label('significant_genes_count')
                )
                .join(Pathway.association_table)
                .filter(Pathway.reactome.isnot(None))
                .group_by(Pathway)
                .having(
                    and_(
                        text('gene_count > 10'),
                        text('gene_count < 500'),
                        text('significant_genes_count > 5')
                    )
                )
            )

        def mapper(results):
            pathway, all_genes, significant_genes = results
            json = pathway.to_json()
            json['ratio'] = significant_genes / all_genes
            json['significant_genes_count'] = significant_genes
            return json

        ajax_view = AjaxTableView.from_query(
            query_constructor=query_constructor,
            results_mapper=mapper,
            search_filter=lambda q: Pathway.description.like(q + '%')
        )
        """
        filters_class=GeneViewFilters,
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
        """
        return ajax_view(self)
