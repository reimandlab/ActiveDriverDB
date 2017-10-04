from flask import jsonify
from flask import request
from sqlalchemy import and_
from sqlalchemy import asc
from sqlalchemy import desc
from sqlalchemy.exc import StatementError
from sqlalchemy.ext.associationproxy import AssociationProxy
from database import db, fast_count
from helpers.filters import joined_query

ordering_functions = {
    'desc': desc,
    'asc': asc
}


def json_results_mapper(result):
    return result.to_json()


class ModelCounter:

    def __init__(self, model):
        self.query = model.query

    def count(self):
        return fast_count(self.query)

    def filter(self, *args, **kwargs):
        self.query = self.query.filter(*args, **kwargs)
        return self


class AjaxTableView:

    @staticmethod
    def from_model(model, **kwargs):

        def prepare_for_sorting(query, sorted_field_name):
            sorted_field = getattr(model, sorted_field_name)

            if type(sorted_field) is AssociationProxy:
                remote_model = (
                    sorted_field.remote_attr.property.
                    parent.class_
                )
                query = query.join(remote_model, sorted_field.local_attr)
                sorted_field = sorted_field.remote_attr

            return query, sorted_field

        return AjaxTableView.from_query(
            query=model.query,
            prepare_for_sorting=prepare_for_sorting,
            count_query_constructor=lambda sql_filters, required_joins: ModelCounter(model),
            **kwargs
        )

    # TODO: use `if callable` instead of `_constructor`
    @staticmethod
    def from_query(
        query=None, count_query=None,
        results_mapper=json_results_mapper, filters_class=None,
        search_filter=None, preset_filter=None,
        query_constructor=None, default_search_sort=None,
        prepare_for_sorting=None, count_query_constructor=None,
        **kwargs
    ):

        args = {
            'sort': None,
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
                sql_filters, manual_filters, required_joins = divided_filters
                if manual_filters:
                    raise ValueError(
                        'From query can only apply filters implementing'
                        ' sqlalchemy interface'
                    )
            else:
                sql_filters = []
                required_joins = []

            if query_constructor:
                query = query_constructor(sql_filters, required_joins)
            else:
                query = joined_query(predefined_query, required_joins)
                if filters_class:
                    filters += sql_filters

            sorted_by_search = False

            sort_key = args['sort']

            if args['sort'] and prepare_for_sorting:
                query, sort_key = prepare_for_sorting(query, args['sort'])

            if args['search'] and default_search_sort:
                query, sorted_by_search = default_search_sort(query, args['search'], sort_key)

            if not sorted_by_search and sort_key:
                query = query.order_by(
                    ordering_function(sort_key)
                )

            if count_query_constructor:
                count_query = count_query_constructor(sql_filters, required_joins)
            elif predefined_count_query:
                count_query = joined_query(predefined_count_query, required_joins)
            else:
                count_query = query

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
