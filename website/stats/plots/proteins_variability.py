from analyses.variability_in_population import does_median_differ_significances, proteins_variability_by_ptm_presence

from helpers.plots import grouped_box_plot, p_value_annotations

from ..store import cases
from .common import site_types_names, any_site_type, motifs


variability_cases = cases(
    site_type=site_types_names + [any_site_type],
    by_counts=[None, True]
).set_mode('product')


@variability_cases
@grouped_box_plot
def by_ptm_presence(site_type, by_counts):
    return proteins_variability_by_ptm_presence(site_type, by_counts)


glycosylation_motifs_cases = cases(by_counts=[None, True], motif=motifs).set_mode('product')


@glycosylation_motifs_cases
@grouped_box_plot
def by_ptm_presence_glycosylation(by_counts, motif):
    return proteins_variability_by_ptm_presence('glycosylation', by_counts, motif.pattern)


@variability_cases
def by_ptm_presence_significance(site_type, by_counts):
    results = proteins_variability_by_ptm_presence(site_type, by_counts)
    significances = does_median_differ_significances(results)
    return p_value_annotations(results, significances)


@glycosylation_motifs_cases
def by_ptm_presence_significance_glycosylation(by_counts, motif):
    results = proteins_variability_by_ptm_presence('glycosylation', by_counts, motif.pattern)
    significances = does_median_differ_significances(results)
    return p_value_annotations(results, significances)
