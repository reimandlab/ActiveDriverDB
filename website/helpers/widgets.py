
class Widget:

    def __init__(
        self, title, template, data, target_name, labels=None, value=None
    ):
        self.title = title
        self.target_name = target_name
        self.template = template
        self.data = data    # list of choices, text for input or textarea
        # labels to be exposed for a widget
        # (some widgets does not accept or does not require labels) (?TODO)
        self._value = value
        self.labels = labels if labels else data

    @property
    def items(self):
        return zip(self.data, self.labels)

    @property
    def nullable(self):
        return True

    @property
    def value(self):
        return self._value

    @property
    def visible(self):
        return True

    @property
    def is_active(self):
        """Should the widget be considered active (set, on) or not"""
        return True


class FilterWidget(Widget):

    def __init__(
        self, title, template, filter, labels=None,
        associated_comparator_widget=None
    ):
        self.filter = filter
        data = filter.allowed_values
        target_name = 'filter[' + filter.id + ']'
        super().__init__(title, template, data, target_name, labels)
        self.comparator_widget = associated_comparator_widget

    @property
    def value(self):
        return self.filter.value

    @property
    def visible(self):
        return self.filter.visible

    @property
    def nullable(self):
        return self.filter.nullable

    @property
    def is_active(self):
        """Should the widget be considered active (set, on) or not"""
        return self.filter.is_active


class FilterComparatorWidget(Widget):

    comparator_names = {
        'eq': '=',
        'lt': '<',
        'gt': '>',
        'ge': '>=',
        'le': '<=',
        'in': 'in',
        'ni': 'inversed in'
    }

    def __init__(self, title, template, filter, labels=None):
        self.filter = filter
        data = filter.allowed_comparators
        labels = [
            self.comparator_names[cmp]
            for cmp in filter.allowed_comparators
        ]
        target_name = 'filter[' + filter.id + '][cmp]'
        super().__init__(title, template, data, target_name, labels)

    @property
    def value(self):
        return self.filter.comparator
