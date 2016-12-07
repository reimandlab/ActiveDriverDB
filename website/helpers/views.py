from flask import request
from flask import jsonify
from sqlalchemy import asc
from sqlalchemy import desc
from sqlalchemy.ext.associationproxy import AssociationProxy
from sqlalchemy import func


def fast_count(query):
    return query.session.execute(
        query.statement.with_only_columns([func.count()]).order_by(None)
    ).scalar()


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

        if args['sort']:
            sorted_field = getattr(model, args['sort'])

            if type(sorted_field) is AssociationProxy:
                remote_model = sorted_field.remote_attr.property.parent.class_
                query = query.join(remote_model, sorted_field.local_attr)
                sorted_field = sorted_field.remote_attr

            query = query.order_by(
                ordering_function(sorted_field)
            )

        if args['search'] and search_filter:
            query = query.filter(search_filter(args['search']))

        elements = query.limit(args['limit']).offset(args['offset']).all()

        return jsonify({
            'total': fast_count(query),
            'rows': [
                element.to_json()
                for element in elements
            ]
        })

    return ajax_table_view
