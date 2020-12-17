from collections import defaultdict
from pathlib import Path

from helpers.plots import grouped_box_plot, p_value_annotations, box_plot
from helpers.cache import cache_decorator, Cache

from analyses.enrichment import ptm_on_random
from models import InheritedMutation, MC3Mutation, lru_cache

from ..store import cases
from .common import site_types_with_any


muts_cases = cases(site_type=site_types_with_any, mode=['occurrences', 'distinct']).set_mode('product')


@lru_cache()
def ptm_muts_enrichment_frequency(site_type, mode):
    groups = defaultdict(dict)
    significances = {}
    sources_and_filters = {
        MC3Mutation: ('TCGA', None),
        InheritedMutation: (
            'ClinVar (pathogenic, likely pathogenic, drug response)',
            InheritedMutation.significance_filter('strict')
        )
    }
    repeats = 100000
    for source, (name, filters) in sources_and_filters.items():
        observed, expected, region, p = ptm_on_random(
            source=source, site_type=site_type.name,
            mode=mode, mutation_filter=filters,
            repeats=repeats
        )
        groups['Randomly drawn mutations (expected #)'][name] = [e / region for e in expected]
        groups[f'{site_type.name.title()} mutations (observed #)'][name] = [o / region for o in observed]
        if p == 0:
            p = f'< 10^-{len(str(repeats)) - 1}'
        significances[name] = p
    return groups, significances


@muts_cases
@grouped_box_plot
def ptm_muts_frequency(site_type, mode):
    groups, significances = ptm_muts_enrichment_frequency(site_type, mode)
    return groups


@muts_cases
def ptm_muts_frequency_significance(site_type, mode):
    groups, significances = ptm_muts_enrichment_frequency(site_type, mode)
    return p_value_annotations(groups, significances)


MODES = ['occurrences', 'distinct']
muts_cases = cases(source=[MC3Mutation, InheritedMutation], site_type=site_types_with_any, mode=MODES).set_mode('product')
cached = cache_decorator(Cache('.enrichment_plot_cache'))


@cached
def ptm_muts_enrichment(source, site_type, mode, repeats=1000000):
    boxes = {}
    sources_and_filters = {
        MC3Mutation: ('TCGA', None),
        InheritedMutation: (
            'ClinVar (pathogenic)',
            InheritedMutation.significance_set_filter('pathogenic')
        )
    }
    name, filters = sources_and_filters[source]
    observed, expected, region, p = ptm_on_random(
        source=source, site_type=site_type.name,
        mode=mode, mutation_filter=filters,
        repeats=repeats
    )
    boxes['Randomly drawn mutations (expected #)'] = expected
    boxes[f'{site_type.name.title()} mutations (observed #)'] = observed
    if p == 0:
        p = f'< 10^-{len(str(repeats)) - 1}'
    return boxes, p, region


def calc_ptm_muts_all_together(site_type):
    groups = defaultdict(dict)
    significances = {}
    for source in [MC3Mutation, InheritedMutation]:
        for mode in MODES:
            boxes, p, region = ptm_muts_enrichment(source, site_type, mode)
            name = f'{source.name}, {mode}'
            significances[name] = p
            for key, box in boxes.items():
                groups[key][name] = box
    return groups, significances


def ggplot2_plot(func, width=1400, height=900, dpi=72):
    dummy_cases = cases()(lambda x: x)

    def wrapper(*args, **kwargs):
        ggplot2 = func(*args, **kwargs)
        print(func.__name__)
        path = Path('static') / f'{func.__name__}_{dummy_cases.full_case_name(kwargs)}.png'
        path = str(path)
        ggplot2.ggsave(path, width=width / dpi, height=height / dpi, dpi=dpi, units='in', bg='transparent')
        return {'path': path}
    return wrapper


@cached
def ptms_enrichment_for_ggplot(site_type):
    from pandas import DataFrame
    rows = []

    significances = []
    source_labels = {
        'MC3': 'TCGA',
        'ClinVar': 'ClinVar (clinically significant)'
    }
    for source in [MC3Mutation, InheritedMutation]:
        for mode in MODES:
            boxes, p, region = ptm_muts_enrichment(source, site_type, mode)
            name = f'{source_labels[source.name]}, {mode}'
            for key, box in boxes.items():
                for value in box:
                    rows.append({
                        'observered_or_expected': key,
                        'group': name,
                        'mode': mode,
                        'count': value,
                        'source': source_labels[source.name]
                    })
            significances.append({
                'pvalue': str(p),
                'group': name,
                'max': max(max(box) for box in boxes.values()),
                # note: the key is random (meaningless for visualisation)
                'observered_or_expected': key,
                'source':  source_labels[source.name],
                'mode': mode
            })

    df = DataFrame(rows)
    d = DataFrame(significances)
    return d, df


ggplot_cases = cases(site_type=site_types_with_any, with_facets=[True, False, 'wrap']).set_mode('product')


@ggplot_cases
@ggplot2_plot
def ptm_muts_all_together(site_type, with_facets=True):
    from helpers.ggplot2 import GG
    from rpy2.robjects.packages import importr
    from rpy2.robjects import StrVector

    d, df = ptms_enrichment_for_ggplot(site_type)
    ggplot2 = importr('ggplot2')
    ggsignif = importr('ggsignif')

    theme_options = {
        'axis.text.x': ggplot2.element_text(angle=0, hjust=0.5),
        'axis.text': ggplot2.element_text(size=15),
        'text': ggplot2.element_text(size=15),
        'legend.text': ggplot2.element_text(size=15),
        'legend.position': 'bottom',
        'strip.text': ggplot2.element_text(size=16),
    }
    fill = 'observed_or_expected'
    levels = ','.join([repr(a) for a in sorted(set(df['observed_or_expected']), reverse=True)])
    fill = f'factor({fill}, levels = c({levels}))'

    if with_facets:
        x = 'observed_or_expected'
        x = f'factor({x}, levels = c({levels}))'
        d['max'] *= 1.1
        x_label = ''
        if with_facets == 'wrap':
            # theme_options['axis.text.x'] = ggplot2.element_blank()
            pass
    else:
        x = 'group'
        xmin = xmax = x
        x_label = 'Mutation source, counting mode'

    plot = (
        GG(ggplot2.ggplot(df, ggplot2.aes_string(x=x, y='count', fill=fill))) +
        ggplot2.geom_boxplot(notch=True, **{'outlier.alpha': 0.1}) +
        ggplot2.theme(**theme_options) +
        ggplot2.labs(x=x_label, y=r'Mutations count', fill='Mutations group') +
        ggplot2.scale_fill_manual(values=StrVector(["#f1a340", '#cccccc'][::-1]))
        #ggplot2.geom_jitter(width=0.1)
    )
    if with_facets:
        plot += ggsignif.geom_signif(data=d, mapping=ggplot2.aes_string(xmin=1, xmax=2, annotations='pvalue', y_position='max'), manual=True, tip_length=0.03, textsize=5.5)
        labels = {'distinct': 'Distinct mutations', 'occurrences': 'Occurrences'}
        def get_facet_label(factors):
            # TODO?
            return factors
        if with_facets == 'wrap':
            plot += ggplot2.facet_wrap('group', scale='free_y', labeller=get_facet_label, nrow=1)
            plot += ggplot2.scale_x_discrete(labels=StrVector(["expected #", "observed #"]))
        else:
            plot += ggplot2.facet_grid('source~mode', scale='free_y', labeller=get_facet_label)
    else:
        plot += ggsignif.geom_signif(data=d, mapping=ggplot2.aes_string(xmin=xmin, xmax=xmax, annotations='pvalue', y_position='max'), manual=True, tip_length=0, textsize=5.5)

    return ggplot2


@cases(site_type=site_types_with_any)
@grouped_box_plot
def ptm_muts_all_together_2(site_type):
    groups, significances = calc_ptm_muts_all_together(site_type)
    return groups


@cases(site_type=site_types_with_any)
def ptm_muts_all_together_significance(site_type):
    groups, significances = calc_ptm_muts_all_together(site_type)
    return p_value_annotations(groups, significances)


@muts_cases
@box_plot
def ptm_muts(source, site_type, mode):
    boxes, significance, region = ptm_muts_enrichment(source, site_type, mode)
    return boxes


@muts_cases
def ptm_muts_significance(source, site_type, mode):
    boxes, significance, region = ptm_muts_enrichment(source, site_type, mode)
    from numpy import percentile
    return [
        {
            'x': 1,
            'y': max(
                percentile(
                    [float(x) for x in box],
                    75
                ) for box in boxes.values()
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
    ]
