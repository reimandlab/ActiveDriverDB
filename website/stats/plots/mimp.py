from analyses.mimp import glycosylation_sub_types, run_mimp
from helpers.plots import stacked_bar_plot

from ..store import counter


@counter
@stacked_bar_plot
def gains_and_losses_for_glycosylation_subtypes():
    results = {}
    effects = 'loss', 'gain'
    for source_name in ['mc3', 'clinvar']:
        for site_type_name in glycosylation_sub_types:
            result = run_mimp(source_name, site_type_name, enzyme_type='catch-all')
            if result.empty:
                continue
            effect_counts = result.effect.value_counts()
            results[source_name] = effects, [
                int(effect_counts.get(effect, 0))
                for effect in effects
            ]
    return results
