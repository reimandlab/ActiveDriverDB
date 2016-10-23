"""Implementation of filters to be used with Ajax and URL based queries"""
import operator
import re
from collections import namedtuple
from collections import defaultdict
from urllib.parse import unquote
from collections import Iterable


def is_iterable_but_not_str(obj):
    return isinstance(obj, Iterable) and not isinstance(obj, str)


class ValidationError(Exception):
    pass


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
        self, targets, attribute, default=None, nullable=True,
        comparators='__all__', choices='__all__',
        default_comparator=None, multiple=False
    ):
        if comparators != '__all__':
            if not default_comparator and len(comparators) == 1:
                default_comparator = comparators[0]
            for comparator in comparators:
                assert comparator in self.possible_comparators.keys()
        self.allowed_comparators = comparators
        self.allowed_values = choices
        if not is_iterable_but_not_str(targets):
            targets = [targets]
        self.targets = targets
        self.primary_target = targets[0]
        self.default = default
        self.attribute = attribute
        self.multiple = multiple    # specify behaviour for multiple-value
        # filtering (either 'any' (or) or 'all' (and)).
        self.nullable = nullable
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
        return self.primary_target.__name__ + '.' + self.attribute

    def _verify_value(self, value):
        if not (
                self.nullable or
                value
        ):
            raise ValidationError(
                'Filter %s is not nullable' % self.id
            )
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
            raise ValidationError(
                'Filter % recieved forbidden value: %s. Allowed: %s' %
                (self.id, value, self.allowed_values)
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
            raise ValidationError(
                'Filter %s recieved forbidden comparator: %s. Allowed: %s' %
                (self.id, comparator, self.allowed_comparators)
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

    def get_multiple_function(self):
        if self.multiple and is_iterable_but_not_str(self.value):
            return self.possible_join_operators[self.multiple]

    def compare(self, value):
        comparator_function = self.possible_comparators[self.comparator]
        multiple_test = self.get_multiple_function()

        return self._compare(value, comparator_function, multiple_test)

    def _compare(self, value, comparator_function, multiple_test):

        # tricky: check if operator is usable on given value.
        # Detects when one tries to check if x in None or y > "tree".
        # As all of those are incorrect false will be returned.
        try:
            comparator_function(value, value)
        except TypeError:
            return False

        if multiple_test:
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
        """Optimized equivalent to list(filter(my_filter.test, elements))"""

        if self.value is None:
            # the filter is turned off
            return -1

        attr_get = operator.attrgetter(self.attribute)

        comparator_function = self.possible_comparators[self.comparator]
        multiple_test = self.get_multiple_function()

        compare = self._compare

        return [
            elem
            for elem in elements
            if compare(
                attr_get(elem),
                comparator_function,
                multiple_test
            )
        ]

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

    def __repr__(self):
        return '<Filter {1} ({0}active) with value "{2}">'.format(
            '' if self.is_active else 'in',
            self.id,
            self.value
        )


class FilterManager:
    """Main class used to parse & apply filters' data specified by request.

    All allowed filters have to be registered during initialization."""

    # An example of separators use:
    # mutation.frequency:gt:0.2;mutation.cancer:in:KIRC,COAD
    filters_separator = ';'
    field_separator = ':'
    sub_value_separator = ','

    # a shorthand for structure to update filters
    UpdateTuple = namedtuple('UpdateTuple', ['id', 'comparator', 'value'])

    def __init__(self, filters):
        # let each filter know where to seek data about other filters
        # (so one filter can relay on state of other filters,
        # eg. be active conditionaly, if another filter is set).

        for filter in filters:
            filter.manager = self

        # store filters as dict of filter_id -> filter for quick access
        self.filters = {
            filter.id: filter
            for filter in filters
        }

    def get_active(self):
        """Return a list of active filters"""
        return [f for f in self.filters.values() if f.is_active]

    def get_inactive(self):
        """Return a list of inactive filters"""
        return [f for f in self.filters.values() if not f.is_active]

    def apply(self, elements):
        """Apply all appropriate filters to given list of elements.

        Only filters targeting the same model and beeing currently active will
        be applied. The target model will be deduced from passed elements.
        """
        try:
            target_type = type(elements[0])
        except IndexError:
            # the list was empty or was emptied before we were able to
            # investigate the type of targeted objects
            return []

        for filter_ in self._get_active_by_target(target_type):
            elements = filter_.apply(elements)
        return elements

    def _get_active_by_target(self, target_type):
        """Return filters which are active & target the same type of objects"""
        return [
            filter_
            for filter_ in self.filters.values()
            if target_type in filter_.targets and filter_.is_active
        ]

    def get_value(self, filter_id):
        """Return value of filter with specified identificator."""
        return self.filters[filter_id].value

    def update_from_request(self, request):
        """Set states of child filters to match those specified in request.

        The query part of request will be looked upon to get filter's data, in
        one of two available formats: modern or fallback.
        Updates for unrecongized filters will be returned as feedback.

        For details see _parse_request() method in this class.
        """
        filter_updates = self._parse_request(request)

        skipped = []
        for update in filter_updates:
            if update.id not in self.filters:
                skipped.append(update)
                continue
            self.filters[update.id].update(
                self._parse_value(update.value),
                self._parse_comparator(update.comparator),
            )
        return skipped

    @staticmethod
    def _parse_fallback_query(query):
        """Parse query in fallback format."""

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

        filters_list = [
            [
                name,
                data.get('cmp', None),    # allow not specyfing comparator -
                # if so, we will use default comparator.
                FilterManager._repr_value(data.get('value'))
            ]
            for name, data in filters.items()
        ]
        return filters_list

    def _parse_request(self, request):
        """Extract and normalize filters' data from Flask's request object.

        Two formats for specifing filters are available:
            modern request format:
                Model.filters=is_ptm:eq:True;Model.frequency:gt:2
            fallback format:
                filter[Model.is_ptm]=True&filter[Model.frequency]=2&\
                filter[Model.frequency][cmp]=gt&fallback=True

        where fallback format is what will be generated by browsers after
        posting HTML form and modern format is designed to be used with AJAX
        requests, to create readable REST interfaces and for internal usage.
        """
        if request.args.get('fallback'):

            query = unquote(str(request.query_string, 'utf-8'))
            filters_list = self._parse_fallback_query(query)

        else:
            string = request.args.get('filters', '')
            filters_list = self._parse_string(string)

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
            filter_update.split(self.field_separator)
            for filter_update in raw_filters
        ]
        return filters_list

    @staticmethod
    def _parse_comparator(comparator):
        if comparator == 'None':
            return None
        return comparator

    @staticmethod
    def _parse_value(value):
        """Safely parse value from string, without eval."""

        if value == 'True':
            return True
        elif value == 'False':
            return False
        elif value == 'None':
            return None

        try:
            return int(value)
        except (ValueError, TypeError):
            pass

        try:
            return float(value)
        except (ValueError, TypeError):
            pass

        value = value.replace('+', ' ')

        if FilterManager.sub_value_separator in value:
            return value.split(FilterManager.sub_value_separator)

        return value

    @staticmethod
    def _repr_value(value):
        """Return string representation of given value (of a filter)."""
        if is_iterable_but_not_str(value):
            return FilterManager.sub_value_separator.join(value)
        return str(value)

    @property
    def url_string(self):
        """String representation of filters from the set for use in URL address.

        Produced string is ready to be included as a query argument in URL path
        """
        return self.filters_separator.join(
            [
                FilterManager.field_separator.join(
                    map(str, [
                        f.id,
                        f.comparator,
                        self._repr_value(f.value)
                    ])
                )
                for f in self.filters.values()
            ]
        )

    def reset(self):
        """Reset values of child filters to bring them into a neutral state."""
        for filter in self.filters.values():
            filter._value = None
