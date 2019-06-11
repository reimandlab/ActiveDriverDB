from pathlib import Path
from typing import Iterable, Mapping

from numpy import percentile
from rpy2.rlike.container import TaggedList
from rpy2.robjects import StrVector, r, IntVector
from rpy2.robjects.packages import importr

from helpers.ggplot2 import GG


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


Pie = Mapping[str, float]


def pie_chart(pies: Mapping[str, Pie]):

    results = []

    for pie_name, pie in pies.items():

        result = {
            'labels': list(pie.keys()),
            'values': list(pie.values()),
            'name': pie_name,
            'type': 'pie'
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

        data_func_with_plot.__name__ = f'plot_of_{data_func.__name__}'
        return data_func_with_plot

    decorator.plot = plotting_func

    return decorator


grouped_box_plot = as_decorator(grouped_box_plot)
box_plot = as_decorator(box_plot)
pie_chart = as_decorator(pie_chart)
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
            'text': 'p-value: ' + (
                f'{significance:.2e}'
                if isinstance(significance, float) else
                f'{significance}'
            ),
            'showarrow': False
        }
        for i, (population_source, significance) in enumerate(significances.items())
    ]


def sequence_logo(
    pwm_or_seq, path: Path=None, width=369, height=149, dpi=72, legend=False,
    renumerate=True, title: str=None, **kwargs
):
    """Generate a sequence logo from Position Weight Matrix (pwm)
    or a list of aligned sequences.

    and save it into a file if a path was provided.
    The logo will be generated with ggseqlogo (R).

    Args:
        pwm_or_seq: list of sequences or PWM matrix or dict where
            keys are names of facets and values are lists or PWMs
        path: where the file should be saved
        renumerate:
            change the labels of x axis to reflect relative position
            to the modified (central) residue (15-aa sequence is assumed)
        width: width in pixels
        height: height in pixels
        dpi: the DPI of the plotting device
        legend: whether and where the legend should be shown
        title: the title of the plot
    """
    gglogo = importr("ggseqlogo")
    ggplot2 = importr("ggplot2")

    if isinstance(pwm_or_seq, list):
        pwm_or_seq = StrVector(pwm_or_seq)
    elif isinstance(pwm_or_seq, dict):
        pwm_or_seq = TaggedList(pwm_or_seq.values(), pwm_or_seq.keys())

    theme_options = {
        'legend.position': legend or 'none',
        'legend.title': ggplot2.element_blank(),
        'legend.text': ggplot2.element_text(size=14),
        'legend.key.size': r.unit(0.2, 'in'),
        'plot.title': ggplot2.element_text(hjust=0.5, size=16),
        'axis.title.y': ggplot2.element_text(size=16),
        'text': ggplot2.element_text(size=20),
        'plot.margin': r.unit([0.03, 0.045, -0.2, 0.06], 'in'),
    }

    plot = GG(gglogo.ggseqlogo(pwm_or_seq, **kwargs)) + ggplot2.theme(**theme_options) + ggplot2.labs(y='bits')

    if renumerate:
        plot += ggplot2.scale_x_continuous(breaks=IntVector(range(1, 14 + 2)), labels=IntVector(range(-7, 7 + 1)))
    if title:
        plot += ggplot2.ggtitle(title)

    if path:
        ggplot2.ggsave(str(path), width=width / dpi, height=height / dpi, dpi=dpi, units='in', bg='transparent')

    return plot
