import json
from flask import request, flash, url_for, redirect, abort, render_template as template
from flask_classful import FlaskView
from website.models import Protein


class SearchView(FlaskView):
    """Enables searching in any of registered database models"""

    models = {
        'protein': Protein
    }

    def index(self, target):
        """Simple input box with selectize-based autocomplete box"""
        return template('search.html', target=target)

    def autocomplete(self, target):
        """Autocompletion API for search for target model (by name)"""
        query = request.args.get('q') or ''

        response = []

        if query:
            model = self.models[target]
            name_filter = model.name.like(query + '%')
            entries = model.query.filter(name_filter).all()
            response = [{'value': entry.name} for entry in entries]

        return json.dumps(response)
