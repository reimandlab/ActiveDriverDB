from flask import render_template as template
from flask import abort
from flask_classful import FlaskView
from flask_classful import route
from models import Pathway
from sqlalchemy import or_
from website.helpers.views import AjaxTableView


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

    @staticmethod
    def _search_filter(query):
        if query.isnumeric():
            return or_(
                Pathway.gene_ontology.like(query + '%'),
                Pathway.reactome.like(query + '%')
            )
        else:
            return Pathway.description.like('%' + query + '%')

    data = route('data')(
        AjaxTableView.from_model(
            Pathway,
            search_filter=_search_filter,
            sort='description'
        )
    )
