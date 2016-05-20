from flask import request, flash, url_for, redirect, abort, render_template as template
from flask_classful import FlaskView, route
from app import app
import json

from models import Protein


@app.route('/')
def index():
    return template('index.html')


class SearchView(FlaskView):

    categories = {
        'protein': Protein
    }

    def index(self, target):
        return template('search.html', target=target)

    def autocomplete(self, target):
        query = request.args.get('q') or ''

        response = []

        if query:
            qrm = self.categories[target]
            name_filter = qrm.name.like(query + '%')
            entries = qrm.query.filter(name_filter).all()
            response = [{'value': entry.name} for entry in entries]

        return json.dumps(response)

SearchView.register(app)


class ProteinView(FlaskView):

    def index(self):
        return SearchView().index(target='protein')

    def show(self, name):
        protein = Protein.query.filter_by(name=name).first_or_404()
        return template('protein.html', protein=protein)

    def mutations(self, name):

        protein = Protein.query.filter_by(name=name).first_or_404()

        mutations_grouped = {}
        for mutation in protein.mutations:
            # for now, I am grouping just by position and cancer
            key = (mutation.position, mutation.cancer_type)
            try:
                mutations_grouped[key] += [mutation]
            except KeyError:
                mutations_grouped[key] = [mutation]

        response = []

        for key, mutations in mutations_grouped.items():
            position, cancer_type = key
            needle = {
                'coord': str(position),
                'value': len(mutations),
                'category': cancer_type
            }
            response += [needle]

        return json.dumps(response)

    def sites(self, name):

        protein = Protein.query.filter_by(name=name).first_or_404()

        response = [
            {
                'coord': str(site.position - 7) + '-' + str(site.position + 7),
                'name': str(site.position) + 'Ph'
            } for site in protein.sites
        ]

        return json.dumps(response)


ProteinView.register(app)
