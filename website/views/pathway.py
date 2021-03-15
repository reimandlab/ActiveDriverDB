from flask import render_template as template, request, jsonify
from flask import abort
from flask_classful import FlaskView
from flask_classful import route

from database import db, levenshtein_sorted
from models import Pathway, GeneList, GeneListEntry, Protein, Gene, source_manager, PathwaysList, PathwaysListEntry
from sqlalchemy import or_, func, and_, text
from helpers.views import AjaxTableView


def search_filter(query):
    if query.isnumeric():
        return or_(
            Pathway.gene_ontology.like(query + '%'),
            Pathway.reactome.like(query + '%')
        )
    else:
        return Pathway.description.ilike('%' + query + '%')


def search_sort(query, q, sort_column, order):
    if sort_column is None or sort_column in ['Pathway.description', 'description', Pathway.description]:
        return levenshtein_sorted(query, Pathway.description, q, order), True
    return query, False


def get_pathway(gene_ontology_id, reactome_id):
    if gene_ontology_id:
        filter_by = {'gene_ontology': gene_ontology_id}
    elif reactome_id:
        filter_by = {'reactome': reactome_id}
    else:
        raise abort(404)
    return Pathway.query.filter_by(**filter_by).one()


class PathwaysView(FlaskView):

    @route('/gene_ontology/<gene_ontology_id>', endpoint='PathwaysView:show')
    @route('/reactome/<reactome_id>', endpoint='PathwaysView:show')
    def show(self, gene_ontology_id=None, reactome_id=None):

        pathway = get_pathway(gene_ontology_id, reactome_id)

        return template('pathway/show.html', pathway=pathway)

    def details(self):
        gene_ontology_id = request.args.get('gene_ontology_id', None)
        reactome_id = request.args.get('reactome_id', None)
        pathway = get_pathway(gene_ontology_id, reactome_id)
        data = pathway.to_json()

        query = (
            db.session.query(Gene.name, func.count(Protein.id))
            .select_from(Pathway)
            .filter(Pathway.id == pathway.id)
            .join(Pathway.association_table)
            .join(Gene)
            .outerjoin(Protein, Gene.id == Protein.gene_id)
            .group_by(Gene)
        )

        isoforms_counts = {
            gene: isoforms_count
            for gene, isoforms_count in query
        }

        for i, gene in enumerate(data['genes']):
            name = gene['name']
            data['genes'][i]['isoforms_count'] = isoforms_counts.get(name, 0)

        return jsonify(data)

    def index(self):
        gene_lists = GeneList.query.all()
        pathways_lists = PathwaysList.query.all()

        matched_lists = [
            {
                'site_type': pathways_list.site_type,
                'mutation_source': pathways_list.mutation_source_name,
                'pathways_list': pathways_list
            }
            for pathways_list in pathways_lists
        ]

        for gene_list in gene_lists:
            matched = False
            for candidate_match in matched_lists:
                if (
                    gene_list.mutation_source_name == candidate_match['mutation_source']
                    and
                    gene_list.site_type == candidate_match['site_type']
                ):
                    matched = True
                    candidate_match['gene_list'] = gene_list
            if not matched:
                matched_lists.append({
                    'pathways_list': None,
                    'gene_list': gene_list,
                    'site_type': gene_list.site_type,
                    'mutation_source': gene_list.mutation_source_name
                })

        for matched_list in matched_lists:
            matched_list['mutation_source_name'] = matched_list['mutation_source']
            matched_list['mutation_source'] = source_manager.source_by_name[matched_list['mutation_source']]

        return template('pathway/index.html', lists=matched_lists)

    def all(self):
        query = request.args.get('query', '')
        return template(
            'pathway/all.html',
            endpoint='all_data',
            endpoint_kwargs={},
            query=query
        )

    def with_significant_genes(self, significant_gene_list_name):
        query = request.args.get('query', '')
        gene_list = GeneList.query.filter_by(name=significant_gene_list_name).first_or_404()
        dataset = source_manager.source_by_name[gene_list.mutation_source_name]
        return template(
            'pathway/with_significant_genes.html',
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
            default_search_sort=search_sort,
            sort='description'
        )
    )

    def significant_data(self, gene_list_id):
        def query_constructor(sql_filters, joins):

            significant_genes = (
                db.session.query(GeneListEntry.gene_id)
                .select_from(GeneListEntry)
                .filter(GeneListEntry.gene_list_id == gene_list_id)
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
            query=query_constructor,
            results_mapper=mapper,
            search_filter=search_filter,
            search_sort=search_sort
        )

        return ajax_view(self)

    def lists(self):
        lists = PathwaysList.query.all()
        return template('pathway/lists.html', lists=lists)

    def list(self, pathways_list_name):
        query = request.args.get('query', '')
        pathways_list = PathwaysList.query.filter_by(name=pathways_list_name).first_or_404()
        dataset = source_manager.source_by_name[pathways_list.mutation_source_name]
        return template(
            'pathway/precomputed.html',
            pathways_list=pathways_list,
            dataset=dataset,
            endpoint='list_data',
            endpoint_kwargs={'pathways_list_id': pathways_list.id},
            query=query
        )

    def list_data(self, pathways_list_id):

        def query_constructor(sql_filters, joins):

            return (
                db.session.query(Pathway, PathwaysListEntry)
                .select_from(Pathway)
                .join(PathwaysListEntry)
                .filter(PathwaysListEntry.pathways_list_id == pathways_list_id)
                .filter(PathwaysListEntry.fdr < 0.1)
            )

        def mapper(results):
            pathway, pathways_list_entry = results
            all_genes = pathways_list_entry.pathway_size
            significant_genes = pathways_list_entry.overlap

            json = pathway.to_json()
            json['ratio'] = len(significant_genes) / all_genes
            json['significant_genes_count'] = len(significant_genes)
            json['fdr'] = pathways_list_entry.fdr

            return json

        ajax_view = AjaxTableView.from_query(
            query=query_constructor,
            results_mapper=mapper,
            search_filter=search_filter,
            search_sort=search_sort
        )

        return ajax_view(self)
