

class Widget:
    """Widget class to be used in templates to create HTML inputs, selects etc.

    Args:
        data: list of choices for select or text for input/textarea
        labels:
            labels to be used by the template. There are some widgets which
            does not accept or does not require labels (widget-specific)
        target_name: corresponds to name attribute in HTML element

    """

    def __init__(
        self, title, template, data, target_name,
        labels=None, disabled_label=None, value=None,
        all_selected_label=None, class_name=''
    ):
        self.title = title
        self.target_name = target_name
        self.template = template
        self.data = data
        self._value = value
        self.labels = labels if labels else data
        self.disabled_label = disabled_label or 'disabled'
        self.all_selected_label = all_selected_label
        self.class_name = class_name

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
        self, title, template, filter, labels=None, disabled_label=None,
        associated_comparator_widget=None, **kwargs
    ):
        self.filter = filter
        data = filter.choices
        target_name = 'filter[' + filter.id + ']'
        super().__init__(
            title, template, data, target_name, labels, disabled_label,
            **kwargs
        )
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
