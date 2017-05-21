from helpers.filters import quote_if_needed, is_iterable_but_not_str


class Widget:
    """Widget class to be used in templates to create HTML inputs, selects etc."""

    def __init__(
        self, title, template, data, target_name,
        labels=None, disabled_label=None, value=None,
        all_selected_label=None, class_name=''
    ):
        """
        Args:
            data: list of choices for select or text for input/textarea
            labels:
                labels to be used by the template. There are some widgets which
                does not accept or does not require labels (widget-specific).

                At most as many labels as elements in data can be provided
                except for case where no data (choices) are provided.

                If there are less labels than elements, the elements without
                a label will be skipped during template generation.

                If labels are provided as mapping (dictionary), the labels
                will be mapped to correspond to given data (key=datum, value=label)

            target_name: corresponds to name attribute in HTML element
        """
        self.title = title
        self.target_name = target_name
        self.template = template
        if not data:
            data = []
        self.data = data
        self._value = value
        if isinstance(labels, dict):
            labels = [
                labels[datum] for datum in data
            ]
        if labels and data and len(labels) > len(data):
            raise ValueError(
                'Number of labels has to be lower '
                'or equal the data elements count.'
            )
        self.labels = labels if labels else data
        self.disabled_label = disabled_label or 'disabled'
        self.all_selected_label = all_selected_label
        self.class_name = class_name

    @property
    def label(self):
        if len(self.labels) > 1:
            raise Exception(
                'Requested for a single label for a widget with multiple '
                'labels %s' % self.title
            )
        if not self.labels:
            return
        return self.labels[0]

    @property
    def items(self):
        data = self.data
        if data:
            data = [quote_if_needed(d) for d in data]
        return zip(data, self.labels)

    @property
    def all_active(self):
        """Are all items active?"""
        return all((quote_if_needed(d) in self.value for d in self.data))

    @property
    def nullable(self):
        return True

    @property
    def value(self):
        if is_iterable_but_not_str(self._value):
            return [quote_if_needed(v) for v in self._value]
        return quote_if_needed(self._value)

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
        self._value = self.filter.value
        return super().value

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

    def __init__(self, title, template, filter):
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
