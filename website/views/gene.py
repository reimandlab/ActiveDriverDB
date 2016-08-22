from flask import render_template as template
from flask_classful import FlaskView
from models import Gene


class GeneView(FlaskView):

    def show(self, gene_name):
        gene = Gene.query.filter_by(name=gene_name).one()
        return template('gene.html', gene=gene)
