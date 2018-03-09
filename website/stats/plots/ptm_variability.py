from helpers.plots import grouped_box_plot, p_value_annotations

from analyses.variability_in_population import (
    ptm_variability_population_rare_substitutions,
    does_median_differ_significances,
)
from ..store import cases
from .common import site_types_names, any_site_type, motifs


@cases(site_type=site_types_names + [any_site_type])
@grouped_box_plot
def population_rare_substitutions(site_type):
    return ptm_variability_population_rare_substitutions(site_type)


@cases(site_type=site_types_names + [any_site_type])
def population_rare_substitutions_significance(site_type):
    results = ptm_variability_population_rare_substitutions(site_type)
    significances = does_median_differ_significances(results, paired=True)
    return p_value_annotations(results, significances)


@cases(motif=motifs)
@grouped_box_plot
def population_rare_substitutions_glycosylation(motif):
    return ptm_variability_population_rare_substitutions('glycosylation', motif.pattern)


@cases(motif=motifs)
def population_rare_substitutions_significance_glycosylation(motif):
    results = ptm_variability_population_rare_substitutions('glycosylation', motif.pattern)
    significances = does_median_differ_significances(results, paired=True)
    return p_value_annotations(results, significances)
