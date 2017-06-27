from flask import jsonify
from flask import request
from sqlalchemy import and_
from sqlalchemy import asc
from sqlalchemy import desc
from sqlalchemy.exc import StatementError
from sqlalchemy.ext.associationproxy import AssociationProxy
from database import db, fast_count


ordering_functions = {
    'desc': desc,
    'asc': asc
}


def json_results_mapper(result):
    return result.to_json()


class AjaxTableView:

    @staticmethod
    def from_model(
        model, results_mapper=json_results_mapper,
        search_filter=None, preset_filter=None, **kwargs
    ):

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
                    remote_model = (
                        sorted_field.remote_attr.property.
                        parent.class_
                    )
                    query = query.join(remote_model, sorted_field.local_attr)
                    sorted_field = sorted_field.remote_attr

                query = query.order_by(
                    ordering_function(sorted_field)
                )

            filters = []

            if preset_filter:
                filters.append(preset_filter)

            if args['search'] and search_filter:
                filters.append(search_filter(args['search']))

            if filters:
                filters_conjunction = and_(*filters)
                query = query.filter(filters_conjunction)

            count = fast_count(query)
            query = query.limit(args['limit']).offset(args['offset'])

            rows = [
                results_mapper(element)
                for element in query
            ]

            return jsonify({
                'total': count,
                'rows': rows
            })

        return ajax_table_view

    @staticmethod
    def from_query(
        query=None, count_query=None,
        results_mapper=json_results_mapper, filters_class=None,
        search_filter=None, preset_filter=None,
        query_constructor=None, **kwargs
    ):

        args = {
            'sort': 'id',
            'search': None,
            'order': 'asc',
            'offset': 0,
            'limit': 25
        }

        args.update(kwargs)

        predefined_query = query
        predefined_count_query = count_query

        def ajax_table_view(self):

            for key, value in args.items():
                args[key] = request.args.get(key, value)

            ordering_function = ordering_functions.get(
                args['order'],
                lambda x: x
            )

            filters = []

            if preset_filter is not None:
                filters.append(preset_filter)

            if args['search'] and search_filter:
                filters.append(search_filter(args['search']))

            if filters_class:
                filters_manager = filters_class()
                divided_filters = filters_manager.prepare_filters()
                sql_filters, manual_filters = divided_filters
                if manual_filters:
                    raise ValueError(
                        'From query can only apply filters implementing'
                        ' sqlalchemy interface'
                    )
            else:
                sql_filters = []

            if query_constructor:
                query = query_constructor(sql_filters)
            else:
                query = predefined_query
                if filters_class:
                    filters += sql_filters

            if args['sort']:

                query = query.order_by(
                    ordering_function(args['sort'])
                )

            if not predefined_count_query:
                count_query = query
            else:
                count_query = predefined_count_query

            if filters:
                filters_conjunction = and_(*filters)
                query = query.filter(filters_conjunction)
                count_query = count_query.filter(filters_conjunction)

            try:
                count = count_query.count()
                query = query.limit(args['limit']).offset(args['offset'])
                elements = query
            except StatementError as e:
                db.session.rollback()
                print(e)
                print('Statement Error detected!')
                return jsonify({'message': 'query error'})

            return jsonify({
                'total': count,
                'rows': [
                    results_mapper(element)
                    for element in elements
                ]
            })

        return ajax_table_view
