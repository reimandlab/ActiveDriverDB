from flask import render_template as template
from flask import abort
from flask import request
from flask import jsonify
from flask_classful import FlaskView
from models import Pathway
from flask_classful import route
# from flask_sqlalchemy import Pagination


class PathwayView(FlaskView):

    @route('/pathway/go/<int:gene_ontology_id>/')
    @route('/pathway/reac/<int:reactome_id>/')
    def show(self, gene_ontology_id=None, reactome_id=None):

        if gene_ontology_id:
            filter_by = {'gene_ontology': gene_ontology_id}
        elif reactome_id:
            filter_by = {'reactome': reactome_id}
        else:
            raise abort(404)
        pathway = Pathway.query.filter_by(**filter_by).one()

        return template('pathway.html', pathway=pathway)

    def table(self):
        return template('pathways.html')

    def data(self):
        from sqlalchemy import asc
        from sqlalchemy import desc
        from sqlalchemy import or_

        ordering_functions = {
            'desc': desc,
            'asc': asc
        }

        search = request.args.get('search', None)
        sort = request.args.get('sort', 'description')
        order = request.args.get('order', 'asc')
        offset = request.args.get('offset', 0)
        limit = request.args.get('limit', 10)

        ordering_function = ordering_functions.get(
            order,
            lambda x: x
        )

        query = Pathway.query

        if search:

            if search.isnumeric():
                search_filter = or_(
                    Pathway.gene_ontology.like(search + '%'),
                    Pathway.reactome.like(search + '%')
                )
            else:
                search_filter = Pathway.description.like('%' + search + '%')

            query = query.filter(search_filter)

        sorted_field = getattr(Pathway, sort)

        query = query.order_by(
            ordering_function(sorted_field)
        )

        pathways = query.limit(limit).offset(offset).all()
        count = query.count()

        return jsonify({
            'total': count,
            'rows': [
                pathway.to_json()
                for pathway in pathways
            ]
        })
