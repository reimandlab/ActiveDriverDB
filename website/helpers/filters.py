"""Implementation of filters to be used with Ajax and URL based queries"""
import operator
import re
from collections import namedtuple
from collections import defaultdict
from urllib.parse import unquote
from collections import Iterable


field_separator = ':'
sub_value_separator = ','


def is_iterable_but_not_str(obj):
    return isinstance(obj, Iterable) and not isinstance(obj, str)


def repr_value(value):
    if is_iterable_but_not_str(value):
        return sub_value_separator.join(value)
    return value


class Filter:

    possible_comparators = {
        'ge': operator.ge,
        'le': operator.le,
        'gt': operator.gt,
        'lt': operator.lt,
        'eq': operator.eq,
        'in': operator.contains,
        'ni': lambda x, y: operator.contains(y, x),
    }

    possible_join_operators = {
        'all': all,
        'any': any,
    }

    def __init__(
        self, name, target, attribute, default=None, nullable=True,
        comparators='__all__', choices='__all__', widget='default',
        default_comparator=None, multiple=False
    ):
        self.widget = widget
        if comparators != '__all__':
            for comparator in comparators:
                assert comparator in self.possible_comparators.keys()
        self.allowed_comparators = comparators
        self.allowed_values = choices
        self.target = target
        self.default = default
        self.attribute = attribute
        self.multiple = multiple    # specify behaviour for multiple-value
        # filtering (either 'any' (or) or 'all' (and)).
        self.nullable = nullable
        self.name = name
        self._value = None
        self.manager = None
        if default_comparator:
            self._verify_comparator(default_comparator)
        self._default_comparator = default_comparator
        self._comparator = None
        if default:
            assert default_comparator

    @property
    def id(self):
        return self.target.__name__ + '.' + self.attribute

    def _verify_value(self, value):
        if not (
                self.nullable or
                value
        ):
            raise Exception('Filter ' + self.name + ' is not nullable')
        if not (
                self.allowed_values == '__all__' or
                value in self.allowed_values or
                (
                    is_iterable_but_not_str(value) and
                    all(
                        sub_value in self.allowed_values
                        for sub_value in value
                    )
                )
        ):
            raise Exception(
                'Filter ' + self.name + ' recieved forbiddden value'
            )

    def _verify_comparator(self, comparator):
        if not (
                (
                    self.allowed_comparators == '__all__' and
                    comparator in self.possible_comparators.keys()
                )
                or
                comparator in self.allowed_comparators
        ):
            raise Exception(
                'Filter ' + self.name + ' recieved forbiddden comparator: ' + comparator
            )

    def _verify(self, value, comparator):
        self._verify_value(value)
        self._verify_comparator(comparator)

    def update(self, value, comparator=None):
        if comparator:
            self._verify_comparator(comparator)
            self._comparator = comparator
        if value is not None:
            self._verify_value(value)
            self._value = value

    def compare(self, value):
        comparator_function = self.possible_comparators[self.comparator]

        if self.multiple and is_iterable_but_not_str(self.value):
            multiple_test = self.possible_join_operators[self.multiple]
            return multiple_test(
                comparator_function(value, sub_value)
                for sub_value in self.value
            )

        return comparator_function(value, self.value)

    def test(self, obj):
        """Test if a given object (instance) passes criteria of this filter.

        If a property does not exists in tested object -1 will be returned,
        to indicate that the filter is not applicable to the passed object.

        Example: filter(my_filter.test, list_of_model_objects)
        Note that an object without tested property will remain on the list.
        """
        if self.value is None:
            # the filter is turned off
            return -1

        obj_value = getattr(obj, self.attribute)
        return self.compare(obj_value)

    def apply(self, elements):
        return list(filter(lambda element: self.test(element), elements))

    @property
    def is_active(self):
        return bool(self.value) and self.visible

    @property
    def value(self):
        if self._value is not None:
            return self._value
        return self.default

    @property
    def comparator(self):
        if self._comparator:
            return self._comparator
        return self._default_comparator

    @property
    def visible(self):
        return True

    def __str__(self):
        value = self.value

        return field_separator.join(
            map(str, [
                self.name,
                self.comparator,
                repr_value(value)
            ])
        )

    def __repr__(self):
        return '<Filter {1} ({0}active) with value "{2}">'.format(
            '' if self.is_active else 'in',
            self.name,
            self.value
        )


class FilterManager:

    filters_separator = ';'
    UpdateTuple = namedtuple('UpdateTuple', ['id', 'comparator', 'value'])

    def __init__(self, filters):
        for filter in filters:
            filter.manager = self

        self.filters = {
            filter.id: filter
            for filter in filters
        }

    def get_active(self):
        #return [f for f in self.filters.values() if f.is_active]
        return list(filter(lambda f: f.is_active, self.filters.values()))

    def get_inactive(self):
        return list(filter(lambda f: not f.is_active, self.filters.values()))

    def apply(self, target_type, elements):
        for _filter in self._get_active_by_target(target_type):
            elements = _filter.apply(elements)
        return elements

    def _get_active_by_target(self, target_type):
        return [
            filter
            for filter in self.filters.values()
            if filter.target == target_type and filter.is_active
        ]

    def get_value(self, filter_id):
        return self.filters[filter_id].value

    def update_from_request(self, request):
        filter_updates = self._parse_request(request)
        for update in filter_updates:
            self.filters[update.id].update(
                self._parse_value(update.value),
                # parse comparator inline
                None if update.comparator == 'None' else update.comparator,
            )

    @staticmethod
    def _parse_fallback_query(query):
        """Parse query in fallback format to a dict of dicts."""

        re_value = re.compile(r'filter\[([\w\.]+)\]')
        re_cmp = re.compile(r'filter\[([\w\.]+)\]\[cmp\]')

        filters = defaultdict(lambda: defaultdict(list))

        for entry in query.split('&'):
            key, value = entry.split('=')

            match = re_value.fullmatch(key)
            if match:
                name = match.group(1)
                filters[name]['value'].append(value)

            match = re_cmp.fullmatch(key)
            if match:
                name = match.group(1)
                filters[name]['cmp'] = value

        return filters

    def _parse_request(self, request):
        """Create a group of filters basing of Flask's request object.

        For browser that sent request with AJAX it just passes 'filters'
        argument from request to 'from_string' classmethod. For browsers
        without JS it parses query in a 'fallback format' that is a long
        format generated automatically from form, with PHP-like syntax.

        Modern request format:
            filters=is_ptm eq True;frequency gt 2
        Fallback format:
            filter[is_ptm]=True&filter[frequency]=2&filter[frequency][cmp]=gt&fallback=True
        """
        if request.args.get('fallback'):

            query = unquote(str(request.query_string, 'utf-8'))
            filters_dict = self._parse_fallback_query(query)

            join_fields = field_separator.join
            filters_list = [
                join_fields([
                    name,
                    data.get('cmp', 'eq'),
                    str(repr_value(data.get('value')))
                ])
                for name, data in filters_dict.items()
            ]
            string = self.filters_separator.join(filters_list)
        else:
            string = request.args.get('filters', '')

        return self._parse_string(string)

    def _parse_string(self, filters_string):
        """Create a group of filters from string.

        Example:
            x = FilterSet.from_string('is_ptm eq 1; is_ptm_direct eq 0')

            will create set of filters that will positively
            evaluate PTM mutations located in flanks
        """
        raw_filters = filters_string.split(self.filters_separator)
        # remove empty strings
        raw_filters = filter(bool, raw_filters)

        return [
            self.UpdateTuple(*filter_update.split(field_separator))
            for filter_update in raw_filters
        ]

    @staticmethod
    def _parse_value(value):
        """Safely parse value from string, without eval"""

        try:
            return int(value)
        except ValueError:
            pass

        try:
            return float(value)
        except ValueError:
            pass

        if value == 'True':
            return True
        elif value == 'False':
            return False
        elif value == 'None':
            return None

        value = value.replace('+', ' ')

        if sub_value_separator in value:
            return value.split(sub_value_separator)

        return value

    @property
    def url_string(self):
        """String represntation of filters from the set for use in URL address.

        Produced string is ready to be included as a query argument in URL path
        """
        return self.filters_separator.join(
            [
                str(f)
                for f in self.filters.values()
            ]
        )

    def reset(self):
        for filter in self.filters.values():
            filter._value = None
