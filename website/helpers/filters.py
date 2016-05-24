"""Implementation of filters to be used with Ajax and URL based queries"""
import operator


class Filter:
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

    def __init__(self, name, comparator, value):

        assert name and comparator and value

        self.name = name
        self.comparator_name = comparator
        self.comparator_func = self.comparators[comparator]

        if value.isnumeric():
            value = float(value)

        self.value = value

    @classmethod
    def from_string(cls, entry):
        """Create a filter from string.

        Example: Filter.from_string('is_ptm eq 1')
        """
        name, comparator, value = entry.split(' ')
        return cls(name, comparator, value)

    def test(self, obj):
        """Test if a given object (instance) passes criteria of this filter.
        If a property does not exists in tested object -1 will be returned,
        to indicate that the filter is not applicable to the passed object.

        Example: filter(my_filter.test, list_of_model_objects)
        Note that an object without tested property will remain on the list.
        """
        try:
            obj_val = getattr(obj, self.name)
            return self.comparator_func(obj_val, self.value)
        except AttributeError:
            # the filter is not applicable
            return -1


class FilterSet:
    """Group of filters that can be parsed or testes at once.

    An object has to pass tests of all filters to pass the FilterSet
    test (subsequent filters' tests are always joined with 'and')
    """

    def __init__(self, filters):
        self.filters = filters

    @classmethod
    def from_string(cls, filters_string):
        """Create a group of filters from string.

        Example:
            x = FilterSet.from_string('is_ptm eq 1; is_ptm_direct eq 0')

            will create set of filters that will positively
            evalueate PTM mutations located in flanks
        """
        raw_filters = filters_string.split(';')
        # remove empty strings
        raw_filters = filter(bool, raw_filters)

        new_filter = Filter.from_string
        filters = [new_filter(filter_str) for filter_str in raw_filters]

        return cls(filters)

    def test(self, obj):
        """Test if an object (obj) passes tests of all filters from the set."""
        for condition in self.filters:
            if not condition.test(obj):
                return False
        return True
