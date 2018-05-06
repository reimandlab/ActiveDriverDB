from collections import defaultdict

from helpers.plots import grouped_box_plot, p_value_annotations

from analyses.enrichment import ptm_on_random
from models import InheritedMutation, MC3Mutation, lru_cache
from ..store import cases
from .common import site_types_with_any


muts_cases = cases(site_type=site_types_with_any, mode=['occurrences', 'distinct']).set_mode('product')


@lru_cache()
def ptm_muts_enrichment(site_type, mode):
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
        observed, expected, p = ptm_on_random(
            source=MC3Mutation, site_type=site_type.name,
            mode=mode, mutation_filter=filters,
            repeats=repeats
        )
        groups['Randomly drawn mutations (expected #)'][name] = expected
        groups[f'{site_type.name.title()} mutations (observed #)'][name] = observed
        if p == 0:
            p = f'< 10^-{len(str(repeats)) - 1}'
        significances[name] = p
    return groups, significances


@muts_cases
@grouped_box_plot
def ptm_muts(site_type, mode):
    groups, significances = ptm_muts_enrichment(site_type, mode)
    return groups


@muts_cases
def ptm_muts_significance(site_type, mode):
    groups, significances = ptm_muts_enrichment(site_type, mode)
    return p_value_annotations(groups, significances)
