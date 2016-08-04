from flask import render_template as template, Blueprint
from website.models import Gene

general = Blueprint('general', __name__)


@general.route('/')
def index():
    return template('index.html')


@general.route('/gene/<gene_name>')
def gene_view(gene_name):
    gene = Gene.query.filter_by(name=gene_name).one()
    return template('gene.html', gene=gene)
