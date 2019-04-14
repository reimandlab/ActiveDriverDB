import operator
from functools import lru_cache
from types import MethodType

from helpers.utilities import is_iterable_but_not_str


class ValidationError(Exception):
    pass


class InitializationError(Exception):
    pass


class BasicFilter:
    """Generic class allowing to create lists/iterators of any iterable
    objects that have compliant interface.

    Args:
        targets:
            list of targets against which applying the filter is planned.
            Each target should be given as a class of the object to be targeted.

            One filter (e.g. age filter) can be used against several targets,
            as long as all the targets have the required attribute accessible.

            For example:
                >>> age_filter = BasicFilter(targets=[User, Equipment], attribute='age')

        attribute:
            the name of an attribute in which a value to be compared is stored.

            For example:

                for model of an user which is defined as:
                    >>> class User:
                    >>>     def __init__(self, name): self.name = name
                    >>> user = User('John')
                if one wished to filter users by name,
                the target would be `User` and the attribute would be `'name'`.

            If the value accessed by `getattr(tested_object, attribute)`
            needs to be modified before being used for comparison (i.e
            you want to add custom filtering, aggregation or type casting),
            you may set `custom_attr_getter` method on property accessing the
            value. This mechanism is meant to facilitate in-flight amendments
            to the structures retrieved by SQLAlchemy, which needs to be used
            in other parts of the application as well, as such values cannot
            be modified on the model/column level - because it would affect
            how these values are returned in other parts of the app.

            The attribute can be a method provided that takes no arguments
            (or that all arguments have some default values).

            When more than one target is provided, only the first target is
            considered when deciding whether the attribute is a method or
            when detecting `custom_attr_getter` of the attribute.
        default:
            the value to compare against if a custom value is not provided
        nullable:
            whether setting False-evaluating values is allowed for this filter
        choices:
            allowed values of the filter, given as a list of identifiers
            (strings) or as a dictionary that maps identifiers (strings)
            to non-serializable objects. While currently selected identifier
            of the value is always accessible through `Filter.value` property,
            the mapped value is available in `Filter.mapped_value` and used
            automatically for testing, application of the filter and
            generation of SQLAlchemy query filters.
        multiple:
            specify what condition should be used when testing list-based
            values. Possible values: 'any', 'all'.

            Example: when filtering a list of PTM sites by type, one might
            want to get all sites that are 'ubiquitination' and 'methylation'
            sites simultaneously: multiple='all' should be used.
            Another user would like to get sites that are either
            'ubiquitination' or 'methylation' sites: multiple='any'
            will be a good choice for that.
        comparators:
            names of comparators to be allowed; by default all possible
            comparators are allowed. Do not include custom comparators here.
        default_comparator:
            name of the comparator to be used; if none is specified,
            but only one comparator was provided as by `comparators=['in']`,
            such comparator will be used as a default one.
        custom_comparators:
            a mapping with custom comparators, which may override the pre-defined
            comparing functions (usually taken from `operator` module); should
            be given in form of: {comparator_name: comparing_function}
        skip_if_default:
            if True, the filter will be applied only if the value differs from
            the default one.
    """

    possible_comparators = {
        'and': operator.and_,
        'or': operator.or_,
        'ge': operator.ge,
        'le': operator.le,
        'gt': operator.gt,
        'lt': operator.lt,
        'eq': operator.eq,
        'ne': operator.ne,
        'in': operator.contains,
        'ni': lambda x, y: operator.contains(y, x),
    }

    possible_join_operators = {
        'all': all,
        'any': any,
    }

    def _check_comparators(self, comparators):
        for comparator in comparators:
            if comparator not in self.possible_comparators.keys():
                raise InitializationError(f'Unknown comparator {comparator}')

    def __init__(
        self, targets, attribute, default=None, nullable=True,
        comparators='__all__', choices=None,
        default_comparator=None, multiple=None,
        skip_if_default=False,
        custom_comparators=None
    ):
        # setup and verify comparators
        comparators = {
            name: compare
            for name, compare in self.possible_comparators.items()
            if name in comparators or comparators == '__all__'
        }
        self._check_comparators(comparators)

        if custom_comparators:
            comparators.update(custom_comparators)

        self.allowed_comparators = comparators

        if default_comparator:
            self._verify_comparator(default_comparator)
        elif len(comparators) == 1:
            default_comparator = next(iter(comparators))

        self._default_comparator = default_comparator
        self._comparator = None

        if default and not default_comparator:
            raise InitializationError(
                'When specifying default value, the default comparator '
                'is also required'
            )

        # setup choices
        if isinstance(choices, dict):
            self.choices = list(choices.keys())
            self.mappings = choices
        else:
            self.choices = choices
            self.mappings = None

        # setup targeted model(s)
        self.targets = (
            targets
            if is_iterable_but_not_str(targets)
            else [targets]
        )

        # copy/initialize simple state/config variables
        self.skip_if_default = skip_if_default
        self.default = default
        self.attribute = attribute
        self.multiple = multiple
        self.nullable = nullable
        self._value = None
        self.manager = None

    @property
    def mapped_value(self):
        value = self.value
        if self.mappings and value:
            if isinstance(value, list):
                value = [self.mappings[sub_value] for sub_value in value]
            else:
                value = self.mappings[value]
        return value

    @property
    def primary_target(self):
        return self.targets[0]

    @property
    def id(self):
        return self.primary_target.__name__ + '.' + self.attribute

    def _verify_value(self, value, raise_on_forbidden=True):
        if not (self.nullable or value):
            raise ValidationError(f'Filter {self.id} is not nullable')
        elif self.choices and not (
            not value or
            (
                is_iterable_but_not_str(value) and
                all(
                    sub_value in self.choices
                    for sub_value in value
                )
            ) or
            (
                    not is_iterable_but_not_str(value) and
                    value in self.choices
            )
        ):
            if raise_on_forbidden:
                raise ValidationError(
                    f'Filter {self.id} received forbidden value: {value}. '
                    f'Allowed: {self.choices}. Check types.'
                )
            else:
                return self.choices

    def _verify_comparator(self, comparator):
        if comparator not in self.allowed_comparators:
            raise ValidationError(
                f'Filter {self.id} received forbidden comparator: {comparator}. '
                f'Allowed: {self.allowed_comparators}'
            )

    def _verify(self, value, comparator):
        self._verify_value(value)
        self._verify_comparator(comparator)

    def update(self, value, comparator=None, raise_on_forbidden=True):
        """Update filter with given value and (optionally) comparator.

        If given value (or part of it) is not allowed on the filter
        it will be either returned as rejected or a ValidationError
        will be raise - depending on raise_on_forbidden value.
        """
        rejected = set()
        if comparator:
            self._verify_comparator(comparator)
            self._comparator = comparator

        if self.multiple and not is_iterable_but_not_str(value):
            value = [value]

        accepted_values = self._verify_value(value, raise_on_forbidden)
        if not raise_on_forbidden and accepted_values:
            if self.multiple:
                retained = set(value).intersection(accepted_values)
                rejected = set(value) - retained
                value = list(retained)
            # raise if we cannot fix it
            self._verify_value(value, True)

        self._value = value

        return rejected

    def get_multiple_function(self):
        if self.multiple and is_iterable_but_not_str(self.mapped_value):
            return self.possible_join_operators[self.multiple]

    def compare(self, value):

        comparator_function = self.allowed_comparators[self.comparator]
        multiple_test = self.get_multiple_function()

        compare = self.get_compare_func(comparator_function, multiple_test)

        return compare(value)

    def get_compare_func(self, comparator_function, multiple_test):
        if multiple_test:
            def compare(value):
                # tricky: check if operator is usable on given value.
                # Detects when one tries to check if x in None or y > "tree".
                # As all of those are incorrect false will be returned.
                try:
                    comparator_function(value, value)
                except TypeError:
                    return lambda x: False

                return multiple_test(
                    comparator_function(value, sub_value)
                    for sub_value in self.mapped_value
                )
            return compare

        def compare(value):

            try:
                comparator_function(value, value)
            except TypeError:
                return lambda x: False
            return comparator_function(value, self.mapped_value)

        return compare

    @lru_cache(maxsize=1)
    def attr_getter(self):
        """Attribute getter that passes a value to an method-attribute if needed"""
        # handle custom arguments getters
        if hasattr(self.primary_target, self.attribute):
            field = getattr(self.primary_target, self.attribute)

            if hasattr(field, 'custom_attr_getter'):
                return field.custom_attr_getter
        else:
            field = None

        getter = operator.attrgetter(self.attribute)

        if field and isinstance(field, MethodType):
            def attr_get(element):
                return getter(element)(self.manager)
            return attr_get

        return getter

    def test(self, obj):
        """Test if a given object (instance) passes criteria of this filter.

        If a property does not exists in tested object -1 will be returned,
        to indicate that the filter is not applicable to the passed object.

        Example: filter(my_filter.test, list_of_model_objects)
        Note that an object without tested property will remain on the list.
        """
        if self.mapped_value is None:
            # the filter is turned off
            return -1

        attr_get = self.attr_getter()
        obj_value = attr_get(obj)
        return self.compare(obj_value)

    def apply(self, elements, itemgetter=None):
        """Optimized equivalent to list(filter(my_filter.test, elements))"""

        if self.mapped_value is None:
            # the filter is turned off
            return -1

        if not elements:
            return []

        attr_get = self.attr_getter()
        if itemgetter:
            old_attr_get = attr_get

            def attr_get(element):
                element = itemgetter(element)
                return old_attr_get(element)

        comparator_function = self.allowed_comparators[self.comparator]
        multiple_test = self.get_multiple_function()

        compare = self.get_compare_func(comparator_function, multiple_test)

        return (
            elem
            for elem in elements
            if compare(
                attr_get(elem)
            )
        )

    @property
    def is_active(self):
        """The filter is active if it is visible and has either:
        - a value different than None, or
        - a value that does not equals to the default one

        so if you need your filter to accept None as a value,
        you will need to change the default to a value != None.
        """
        return self.visible and (
            self.value is not None
            or
            self.value != self.default
        )

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

    visible = True

    def __repr__(self):
        return f'<Filter {self.id} ({"" if self.is_active else "in"}active) with value "{self.value}">'
