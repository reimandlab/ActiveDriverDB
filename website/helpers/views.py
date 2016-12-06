from flask import request
from flask import jsonify
from sqlalchemy import asc
from sqlalchemy import desc


ordering_functions = {
    'desc': desc,
    'asc': asc
}


def make_ajax_table_view(model, search_filter=None, **kwargs):

    args = {
        'sort': 'id',
        'search': None,
        'order': 'asc',
        'offset': 0,
        'limit': 25
    }

    args.update(kwargs)

    def ajax_table_view(self):

        for key, value in args.items():
            args[key] = request.args.get(key, value)

        ordering_function = ordering_functions.get(
            args['order'],
            lambda x: x
        )

        query = model.query

        if args['search'] and search_filter:
            query = query.filter(search_filter(args['search']))

        if args['sort']:
            sorted_field = getattr(model, args['sort'])

            query = query.order_by(
                ordering_function(sorted_field)
            )

        elements = query.limit(args['limit']).offset(args['offset']).all()

        return jsonify({
            'total': query.count(),
            'rows': [
                element.to_json()
                for element in elements
            ]
        })

    return ajax_table_view
