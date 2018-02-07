from typing import Iterable, Mapping

from numpy import percentile


def bar_plot(labels: Iterable, values: Iterable, text: Iterable=None, name=None):
    data = {
        'x': list(labels),
        'y': list(values),
        'type': 'bar'
    }
    if text:
        data['text'] = list(text)
        data['hoverinfo'] = 'text'
    if name:
        data['name'] = name
    return [data]


def stacked_bar_plot(grouped_data):
    traces = []
    for name, group in grouped_data.items():
        traces.append(bar_plot.plot(*group, name=name)[0])
    return traces


BoxSet = Mapping[str, list]


def grouped_box_plot(boxes_by_group: Mapping[str, BoxSet]):

    results = []

    for group_name, boxes in boxes_by_group.items():
        names = []
        values = []

        for box_name, box_values in boxes.items():

            names += [box_name] * len(box_values)
            values.extend(box_values)

        result = {
            'y': values,
            'x': names,
            'name': group_name,
            'type': 'box'
        }
        results.append(result)

    return results


def box_plot(boxes: BoxSet):

    results = []

    for box_name, box_values in boxes.items():

        result = {
            'y': box_values,
            'name': box_name,
            'type': 'box'
        }
        results.append(result)

    return results


def as_decorator(plotting_func, unpack=False):
    def decorator(data_func):

        def data_func_with_plot(*args, **kwargs):
            data = data_func(*args, **kwargs)
            if unpack:
                return plotting_func(*data)
            else:
                return plotting_func(data)

        return data_func_with_plot

    decorator.plot = plotting_func

    return decorator


grouped_box_plot = as_decorator(grouped_box_plot)
box_plot = as_decorator(box_plot)
bar_plot = as_decorator(bar_plot, unpack=True)
stacked_bar_plot = as_decorator(stacked_bar_plot)


def p_value_annotations(results, significances):
    return [
        {
            'x': 1 * i,
            'y': max(
                percentile(
                    [float(x) for x in result[population_source]],
                    75
                ) for result in results.values()
            ) * 1.1,
            'xref': 'x',
            'yref': 'y',
            'text': f'p-value: {significance:.2e}',
            'showarrow': False
        }
        for i, (population_source, significance) in enumerate(significances.items())
    ]