import json
from flask import render_template as template
from flask import request
from flask_classful import FlaskView
from flask_classful import route
from sqlalchemy import or_
from website.models import Protein


class SearchView(FlaskView):
    """Enables searching in any of registered database models"""

    models = {
        'proteins': Protein
    }

    @route('/')
    def default(self):
        """Render default search form prompting to search for a protein"""
        return self.index(target='proteins')

    def index(self, target):
        """Render search form and results (if any) for proteins or mutations"""

        query = request.args.get(target) or ''

        if target == 'proteins':
            # handle GET here
            results = self._search(query, target, 20)
        else:
            # TODO
            # expect POST here
            results = {}
            # TODO: redirect with an url conatining session id, so user can save
            # line as a bookmark and return there later

        return template(
            'search/index.html',
            target=target,
            results=results,
            query=query,
        )

    def form(self, target):
        """Return an empty HTML form appropriate for given target"""
        return template('search/form.html', target=target)

    def autocomplete(self, target, limit=20):
        """Autocompletion API for search for target model (by name)"""
        # TODO: implement on client side requests with limit higher limits
        # and return the information about available results (.count()?)
        query = request.args.get('q') or ''

        entries = self._search(query, target, limit)

        response = [
            {
                'value': entry.name,
                'refseq': entry.refseq,
                'html': template('search/gene_results.html', gene=entry)
            }
            for entry in entries
        ]

        return json.dumps(response)

    def _search(self, phase, target, limit=False):
        """Search for a given target with phase"""
        if not phase:
            return []

        model = self.models[target]
        name_filter = model.name.like(phase + '%')

        # looking up both by name and refseq is costly - perform it wisely
        if phase.isnumeric():
            phase = 'NM_' + phase
        if phase.startswith('NM_'):
            refseq_filter = model.refseq.like(phase + '%')
            model_filter = or_(name_filter, refseq_filter)
        else:
            model_filter = name_filter

        orm_query = model.query.filter(model_filter)
        if limit:
            orm_query = orm_query.limit(limit)
        entries = orm_query.all()
        return entries
