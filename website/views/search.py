import json
from flask import render_template as template
from flask import request
from flask_classful import FlaskView
from sqlalchemy import or_
from website.models import Protein


class SearchView(FlaskView):
    """Enables searching in any of registered database models"""

    models = {
        'protein': Protein,
        'network': Protein
    }

    def index(self, target):
        """Simple input box with selectize-based autocomplete box"""
        return template('search.html', target=target)

    def autocomplete(self, target, limit=20):
        """Autocompletion API for search for target model (by name)"""
        # TODO: implement on client side requests with limit higher limits
        # and return the information about available results (.count()?)
        query = request.args.get('q') or ''

        response = []

        if query:
            model = self.models[target]
            name_filter = model.name.like(query + '%')
            refseq_filter = model.refseq.like(query + '%')
            model_filter = or_(name_filter, refseq_filter)
            entries = model.query.filter(model_filter).limit(limit).all()
            response = [
                {'value': entry.name, 'refseq': entry.refseq}
                for entry in entries
            ]

        return json.dumps(response)
