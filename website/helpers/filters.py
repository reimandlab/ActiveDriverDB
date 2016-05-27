"""Implementation of filters to be used with Ajax and URL based queries"""
import operator
from copy import deepcopy


class Filters:

    def __init__(self, active_filters, allowed_filters):

        active_filters.remove_unused()
        available_filters = deepcopy(allowed_filters)

        for passed_filter in active_filters:
            for allowed_filter in available_filters:
                if allowed_filter.property == passed_filter.property:
                    passed_filter.name = allowed_filter.name
                    passed_filter.type = allowed_filter.type
                    available_filters.filters.remove(allowed_filter)
                    break
            else:
                raise Exception('Filter {0} not allowed'.format(passed_filter))

        self.active = active_filters
        self.available = available_filters


class Filter:

    field_separator = ' '

    def __init__(self, property_name, comparator_name, default_value, filter_type, name):
        self.name = name
        self.property = property_name
        self.value = default_value
        self.comparator_name = comparator_name
        self.type = filter_type

    def __str__(self):
        return self.field_separator.join(map(str, [self.property, self.comparator_name, self.value]))


class ObjectFilter(Filter):
    """Single filter that tests if a passed instance has a property
    with value passing the criteria specified during initialization.

    It uses standard Python comaparators.
    """

    comparators = {
        'ge': operator.ge,
        'le': operator.le,
        'gt': operator.gt,
        'lt': operator.lt,
        'eq': operator.eq,
    }

    def __init__(self, property_name, comparator_name, value):

        assert property_name and comparator_name and value

        self.property = property_name
        self.comparator_name = comparator_name
        self.comparator_func = self.comparators[comparator_name]

        try:
            value = int(value)
        except ValueError:
            pass

        try:
            value = float(value)
        except ValueError:
            pass

        if value == 'True':
            value = True
        elif value == 'False':
            value = False
        elif value == 'None':
            value = None

        self.value = value

    @classmethod
    def from_string(cls, entry):
        """Create a filter from string.

        Example: Filter.from_string('is_ptm eq 1')
        """
        property_name, comparator, value = entry.split(cls.field_separator)
        return cls(property_name, comparator, value)

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
        try:
            obj_val = getattr(obj, self.property)
            return self.comparator_func(obj_val, self.value)
        except AttributeError:
            # the filter is not applicable - the property does not exists in obj
            return -1


class FilterSet:
    """Group of filters that can be parsed or testes at once.

    An object has to pass tests of all filters to pass the FilterSet
    test (subsequent filters' tests are always joined with 'and')
    """

    filters_separator = ';'

    def __init__(self, filters):
        self.filters = filters

    def remove_unused(self):
        self.filters = list(filter(lambda x: x.value is not None, self.filters))

    @classmethod
    def from_string(cls, filters_string):
        """Create a group of filters from string.

        Example:
            x = FilterSet.from_string('is_ptm eq 1; is_ptm_direct eq 0')

            will create set of filters that will positively
            evalueate PTM mutations located in flanks
        """
        raw_filters = filters_string.split(cls.filters_separator)
        # remove empty strings
        raw_filters = filter(bool, raw_filters)

        new_filter = ObjectFilter.from_string
        filters = [new_filter(filter_str) for filter_str in raw_filters]

        return cls(filters)

    def __bool__(self):
        return bool(self.filters)

    def test(self, obj):
        """Test if an object (obj) passes tests of all filters from the set."""
        for condition in self.filters:
            if not condition.test(obj):
                return False
        return True

    def __iter__(self):
        """Iteration over FilterSet is an iteration over its filters"""
        return iter(self.filters)

    @property
    def url_string(self):
        """Represntation of filters from the set which can be passed
        as a query argument (get method) in an URL adress"""
        return self.filters_separator.join([str(f) for f in self])
