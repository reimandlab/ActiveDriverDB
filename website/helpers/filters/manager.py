import re
from collections import namedtuple, defaultdict

from sqlalchemy import and_

from helpers.utilities import is_iterable_but_not_str


def quote_if_needed(value):
    if type(value) is not str:
        return value
    q_char = FilterManager.quote_char
    if FilterManager.sub_value_separator in value:
        if not (value.startswith(q_char) and value.endswith(q_char)):
            return q_char + value + q_char
    return value


def split_with_quotation(value):
    from csv import reader

    for v in reader(
        [value],
        delimiter=FilterManager.sub_value_separator,
        quotechar=FilterManager.quote_char
    ):
        return v


def unqoute(value):
    q_char = FilterManager.quote_char
    if value.startswith(q_char) and value.endswith(q_char):
        return value[1:-1]
    return value


def joined_query(query, required_joins, limit_to=None):
    already_joined = set()
    for joins in required_joins:
        for join in joins:
            if limit_to and join not in limit_to:
                continue
            if join not in already_joined:
                from sqlalchemy.exc import InvalidRequestError
                try:
                    query = query.join(join)
                    already_joined.add(join)
                except InvalidRequestError:
                    pass
    return query


class FilterManager:
    """Main class used to parse & apply filters' data specified by request.

    All allowed filters have to be registered during initialization."""

    # An example of separators use:
    # mutation.frequency:gt:0.2;mutation.cancer:in:KIRC,COAD
    filters_separator = ';'
    field_separator = ':'
    sub_value_separator = ','
    quote_char = '\''

    # a shorthand for structure to update filters
    UpdateTuple = namedtuple('UpdateTuple', ['id', 'comparator', 'value'])

    def __init__(self, filters):
        # let each filter know where to seek data about other filters
        # (so one filter can relay on state of other filters,
        # eg. be active conditionally, if another filter is set).

        for filter_ in filters:
            filter_.manager = self

        # store filters as dict of filter_id -> filter for quick access
        self.filters = {
            filter_.id: filter_
            for filter_ in filters
        }

    def prepare_filters(self, target=None):

        to_apply_manually = []
        query_filters = []
        all_required_joins = []

        for the_filter in self._filters_to_apply_to(target):

            if the_filter.has_sqlalchemy:

                the_target = target if target else the_filter.targets[0]

                as_sqlalchemy, required_joins = the_filter.as_sqlalchemy(the_target)
                if as_sqlalchemy is not None:
                    query_filters.append(as_sqlalchemy)
                    all_required_joins.append(required_joins)

            else:
                to_apply_manually.append(the_filter)

        return query_filters, to_apply_manually, all_required_joins

    def build_query(self, target, custom_filter=None, query_modifier=None):
        """There are two strategies of using filter manager:

            - you can get results from database and walk through
              every element in the list, or
            - you can build a query and move some job to the database;
              not always it is possible though.
        """
        query_filters, to_apply_manually, required_joins = self.prepare_filters(target)

        query_filters_sum = and_(*query_filters)

        if custom_filter:
            query_filters_sum = custom_filter(query_filters_sum)

        query = joined_query(target.query, required_joins)
        query = query.filter(query_filters_sum)

        if query_modifier:
            query = query_modifier(query)

        return query, to_apply_manually

    def query_all(self, target, custom_filter=None, query_modifier=None):
        """Retrieve all objects of type 'target' which
        match criteria of currently active filters.
        """

        query, to_apply_manually = self.build_query(target, custom_filter, query_modifier)

        return self.apply(query, to_apply_manually)

    def query_count(self, target, custom_filter=None, query_modifier=None):
        """Retrieve count of all objects of type 'target' which
        match criteria of currently active filters.
        """

        query, to_apply_manually = self.build_query(target, custom_filter, query_modifier)

        if not to_apply_manually:
            return query.with_entities(target.id).count()
        else:
            return len(self.apply(query, to_apply_manually))

    def apply(self, elements, filters_subset=None, itemgetter=None):
        """Apply all appropriate filters to given list of elements.

        Only filters targeting the same model and being currently active will
        be applied. The target model will be deduced from passed elements.
        """
        try:
            tester = elements[0]
            if itemgetter:
                tester = itemgetter(tester)

            target_type = type(tester)
        except IndexError:
            # the list was empty or was emptied before we were able to
            # investigate the type of targeted objects
            return []

        if filters_subset is not None:
            filters = filters_subset
        else:
            filters = self._filters_to_apply_to(target_type)

        for filter_ in filters:
            elements = filter_.apply(elements, itemgetter)

        return list(elements)

    def _filters_to_apply_to(self, target=None):
        """Return filters that are active and can be applied to given target.

        If a filter is set to be omitted by `skip_if_default=True`, it will be
        filtered if the current value of the filter is the save as the default.
        """
        return [
            filter_
            for filter_ in self._active_and_applicable_filters(target)
            if not (filter_.skip_if_default and set(filter_.default) == set(filter_.value))
        ]

    def _active_and_applicable_filters(self, target=None):
        """Return filters which are active & are applicable to given target.

        If no target is given, all active filters will be returned.
        """
        catch_all_active_filters = not target
        return [
            filter_
            for filter_ in self.filters.values()
            if (
                (catch_all_active_filters or target in filter_.targets)
                and
                filter_.is_active
            )
        ]

    def get_value(self, filter_id):
        """Return value of filter with specified identifier."""
        return self.filters[filter_id].value

    def update_from_request(self, request, raise_on_forbidden=True):
        """Set states of child filters to match those specified in request.

        The query part of request will be looked upon to get filter's data, in
        one of two available formats: modern or fallback.

        For details see _parse_request() method in this class.

        Returns:
            tuple: skipped, rejected

            skipped: updates skipped, from unrecognized filters
            rejected: updates skipped, from forbidden values (if raise_on_forbidden was False)
        """
        filter_updates = self._parse_request(request)

        skipped = []
        rejected = defaultdict(list)

        for update in filter_updates:
            if update.id not in self.filters:
                skipped.append(update)
                continue

            rejected_updates = self.filters[update.id].update(
                self._parse_value(update.value),
                self._parse_comparator(update.comparator),
                raise_on_forbidden=raise_on_forbidden
            )

            if rejected_updates:
                rejected[update.id].extend(rejected_updates)

        return skipped, rejected

    def _parse_fallback_query(self, args):
        """Parse query in fallback format."""

        re_value = re.compile(r'filter\[([\w.]+)\]')
        re_cmp = re.compile(r'filter\[([\w.]+)\]\[cmp\]')

        filters = defaultdict(lambda: defaultdict(list))

        for key, value in args.items():

            match = re_value.fullmatch(key)
            if match:
                name = match.group(1)
                filters[name]['value'] = value

            match = re_cmp.fullmatch(key)
            if match:
                name = match.group(1)
                filters[name]['cmp'] = value

        filters_list = [
            [
                filter_name,
                data.get('cmp', None),    # allow not specifying comparator -
                # if so, we will use default comparator.
                self._repr_value(data.get('value'))
            ]
            for filter_name, data in filters.items()
        ]
        return filters_list

    def _parse_request(self, request):
        """Extract and normalize filters' data from Flask's request object.

        Arguments will be extracted from request.args or request.form.

        If arguments contain 'clear_filters' command,
        all other arguments will be ignored.

        Two formats for specifying filters are available:
            modern request format:
                Model.filters=is_ptm:eq:True;Model.frequency:gt:2
            fallback format:
                filter[Model.is_ptm]=True&filter[Model.frequency]=2&\
                filter[Model.frequency][cmp]=gt&fallback=True

        where fallback format is what will be generated by browsers after
        posting HTML form and modern format is designed to be used with AJAX
        requests, to create readable REST interfaces and for internal usage.
        """
        if request.method == 'GET':
            args = request.args
        else:
            args = request.form

        if args.get('clear_filters'):
            filters_list = self._parse_fallback_query({})
        elif args.get('fallback'):
            data = {
                key: value[0] if isinstance(value, list) and len(value) == 1 else value
                for key, value in args.to_dict(flat=False).items()
            }
            filters_list = self._parse_fallback_query(data)
        else:
            filters_list = self._parse_string(
                args.get('filters', '')
            )

        return [
            self.UpdateTuple(*filter_update)
            for filter_update in filters_list
        ]

    def _parse_string(self, filters_string):
        """Split modern query string into list describing filter's settings."""
        raw_filters = filters_string.split(self.filters_separator)

        # remove empty strings
        raw_filters = filter(bool, raw_filters)

        filters_list = [
            filter_update.split(self.field_separator, maxsplit=2)
            for filter_update in raw_filters
        ]
        return filters_list

    @staticmethod
    def _parse_comparator(comparator):
        if comparator == 'None':
            return None
        return comparator

    def _parse_value(self, value, do_not_split=False):
        """Safely parse value from string, without eval.

        For sub-values quotations will be respected.
        """

        if value == 'True':
            return True
        elif value == 'False':
            return False
        elif value == 'None':
            return None
        elif value.isdigit():
            return int(value)

        value = value.replace('+', ' ')

        splitted = split_with_quotation(value)

        if not do_not_split and len(splitted) > 1:
            return [self._parse_value(v, True) for v in splitted]

        value = unqoute(value)

        return value

    def _repr_value(self, value):
        """Return string representation of given value (of a filter)."""
        if is_iterable_but_not_str(value):
            return self.sub_value_separator.join([
                quote_if_needed(str(v))
                for v in value
            ])

        return str(value)

    def url_string(self, expanded=False):
        """String representation of filters from the set for use in URL address.

        Produced string is ready to be included as a query argument in Flask's
        `url_for` func. If no string has been produced, None will be returned.

        Args:
            expanded:
                should all active filters be included
                (also those with value set to default)
        """
        return self.filters_separator.join(
            [
                self.field_separator.join(
                    map(str, [
                        f.id,
                        f.comparator,
                        self._repr_value(f.value)
                    ])
                )
                for f in self.filters.values()
                if f.is_active and (
                    f.value != f.default
                    or expanded
                )
            ]
        ) or None   # if empty string has been built, return None to indicate
        # that there is really nothing interesting (keeps address clean when
        # result is being passed as a keyword arg to flask's url_for function)

    def reset(self):
        """Reset values of child filters to bring them into a neutral state."""
        for filter_ in self.filters.values():
            filter_._value = None

    def reformat_request_url(self, request, endpoint, *args, **kwargs):
        from flask import url_for
        from flask import redirect
        from flask import current_app

        if request.args.get('fallback'):

            scheme = current_app.config.get('PREFERRED_URL_SCHEME', 'http')

            url = url_for(endpoint, *args,  _external=True, _scheme=scheme, **kwargs)

            filters = self.url_string()

            args = dict(request.args)
            # filters might be empty if
            # (e.g. if all are pointing to default values)
            if filters:
                args['filters'] = [filters]

            query_string = '&'.join(
                [
                    arg + '=' + (
                        value[0]
                        if (isinstance(value, list) and len(value) == 1) else
                        value
                    )
                    for arg, value in args.items()
                    if not (arg.startswith('filter[') or arg == 'fallback')
                ]
            )
            # add other arguments
            if query_string:
                url += '?' + query_string

            return redirect(url)
