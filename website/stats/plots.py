from tqdm import tqdm

from analyses.variability_in_population import (
    variability_in_population, group_by_substitution_rates,
    proteins_variability,
)
from models import Plot, The1000GenomesMutation, ExomeSequencingMutation, Site, MC3Mutation, InheritedMutation
from stats.store import CountStore, counter, cases

population_sources = [ExomeSequencingMutation, The1000GenomesMutation]


class Plots(CountStore):

    storage_model = Plot

    @cases(site_type=Site.types())
    @counter
    def ptm_variability_population_rare_substitutions(self, site_type=''):
        """Compare variability of sequence in PTM sites
        with the variability of sequence outside of PTM sites,
        using frequency of rare substitutions.
        """

        results = []

        protein_bins = {}

        print(f'Rare substitutions in PTM/non-PTM regions for: {site_type}')

        for population_source in population_sources:
            protein_bins[population_source] = group_by_substitution_rates(population_source)

        for group, site_type in [('non-PTM', None), ('PTM regions', site_type)]:

            y = []
            x = []
            z = []

            for population_source in population_sources:

                variability = []
                total_muts = []

                for protein_bin in tqdm(protein_bins[population_source]):

                    for percentage, muts_cout in variability_in_population(
                        population_source, site_type,
                        protein_subset=protein_bin
                    ):
                        variability += [percentage]
                        total_muts += [muts_cout]

                y += variability
                x += [population_source.name] * len(variability)
                z += total_muts

                print(f'Total muts in {group}: {sum(z)}')

            result = {
                'y': y,
                'x': x,
                'counts': z,
                'name': group,
                'type': 'box'
            }
            results.append(result)

        return results

    @cases(site_type=Site.types(), by_counts=[True])
    @counter
    def proteins_variability_by_ptm_presence(self, site_type='', by_counts=False):

        results = []

        for group, without_ptm, site_type in [('Without PTM sites', True, None), ('With PTM sites', False, site_type)]:
            y = []
            x = []
            counts = {}

            for population_source in population_sources:

                rates = proteins_variability(
                    population_source, site_type=site_type, without_sites=without_ptm, by_counts=by_counts
                )
                proteins, variability = zip(*rates)

                y += variability
                x += [population_source.name] * len(variability)

                counts[population_source.name] = len(proteins)

            print(f'Proteins distribution for {group} (site_type: {site_type}): {counts}')

            result = {
                'y': y,
                'x': x,
                'proteins_count': counts,
                'name': group,
                'type': 'box'
            }
            results.append(result)

        return results

    @cases(site_type=Site.types())
    @counter
    def most_mutated_sites_mc3(self, site_type=''):
        return self.most_mutated_sites(MC3Mutation, site_type)

    @cases(site_type=Site.types())
    @counter
    def most_mutated_sites_clinvar(self, site_type=''):
        return self.most_mutated_sites(InheritedMutation, site_type)

    @staticmethod
    def most_mutated_sites(source, site_type=''):
        from analyses.enrichment import most_mutated_sites

        sites, counts = zip(*most_mutated_sites(source, site_type, limit=20).all())

        return [
            {
                'x': [f'{site.protein.refseq}:{site.position}{site.residue}' for site in sites],
                'y': counts,
                'type': 'bar'
            }
        ]
