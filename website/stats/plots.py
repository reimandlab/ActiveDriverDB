from pandas import DataFrame
from tqdm import tqdm

from analyses.variability_in_population import (
    variability_in_population, group_by_substitution_rates,
    proteins_variability,
)
from database import db
from models import (
    Plot, The1000GenomesMutation, ExomeSequencingMutation, Site, MC3Mutation, InheritedMutation, Cancer,
    Gene,
    Protein,
    Mutation,
    func,
)
from analyses.active_driver import pan_cancer_analysis, per_cancer_analysis, clinvar_analysis
from .store import CountStore, counter, cases

population_sources = [ExomeSequencingMutation, The1000GenomesMutation]


def bar_plot(func):
    def plot(*args, **kwargs):
        labels, values, *args = func(*args, **kwargs)
        data = {
            'x': list(labels),
            'y': list(values),
            'type': 'bar'
        }
        if args:
            data['text'] = list(args[0])
        return [data]
    return plot


site_types = Site.types()
any_site_type = ''


class Plots(CountStore):

    storage_model = Plot

    @cases(site_type=Site.types())
    @counter
    def ptm_variability_population_rare_substitutions(self, site_type=any_site_type):
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
    def proteins_variability_by_ptm_presence(self, site_type=any_site_type, by_counts=False):

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
    def most_mutated_sites_mc3(self, site_type=any_site_type):
        return self.most_mutated_sites(MC3Mutation, site_type)

    @cases(site_type=Site.types())
    @counter
    def most_mutated_sites_clinvar(self, site_type=any_site_type):
        return self.most_mutated_sites(InheritedMutation, site_type)

    @staticmethod
    @bar_plot
    def most_mutated_sites(source, site_type=any_site_type):
        from analyses.enrichment import most_mutated_sites

        sites, counts = zip(*most_mutated_sites(source, site_type, limit=20).all())

        return [f'{site.protein.gene_name}:{site.position}{site.residue}' for site in sites], counts

    @staticmethod
    def count_mutations_by_gene(source, genes):
        return [
            db.session.query(func.count(source.count))
            .join(Mutation).join(Protein)
            .join(Gene, Gene.preferred_isoform_id == Protein.id)
            .filter(Gene.name == gene).scalar()
            for gene in genes
        ]

    def active_driver_by_muts_count(self, result):
        top_fdr = result['top_fdr']
        mutation_counts = self.count_mutations_by_gene(MC3Mutation, top_fdr.gene)
        return top_fdr.gene, mutation_counts, [f'fdr: {fdr}' for fdr in top_fdr.fdr]

    @cases(site_type=site_types)
    @counter
    @bar_plot
    def pan_cancer_active_driver(self, site_type=any_site_type):
        result = pan_cancer_analysis(site_type)
        return self.active_driver_by_muts_count(result)

    @cases(site_type=site_types)
    @counter
    @bar_plot
    def clinvar_active_driver(self, site_type=any_site_type):
        result = clinvar_analysis(site_type)
        return self.active_driver_by_muts_count(result)

    @cases(cancer_code={cancer.code for cancer in Cancer.query})
    @bar_plot
    def per_cancer_active_driver_glycosylation(self, cancer_code, site_type='glycosylation'):
        results = per_cancer_analysis(site_type)
        try:
            result = results[cancer_code]
        except KeyError:
            print(f'No results for {cancer_code}')
            return [], []
        return self.active_driver_by_muts_count(result)

    @staticmethod
    @bar_plot
    def active_driver_gene_ontology(profile: DataFrame):
        if profile.empty:
            return [], []
        return profile['t name'], profile['Q&T'], [f'p-value: {p}' for p in profile['p-value']]

    @cases(site_type=site_types)
    @counter
    def pan_cancer_active_driver_gene_ontology(self, site_type=any_site_type):
        result = pan_cancer_analysis(site_type)
        return self.active_driver_gene_ontology(result['profile'])

    @cases(site_type=site_types)
    @counter
    def clinvar_active_driver_gene_ontology(self, site_type=any_site_type):
        result = clinvar_analysis(site_type)
        return self.active_driver_gene_ontology(result['profile'])

    @cases(site_type=site_types)
    def pan_cancer_active_driver_gene_ontology_with_bg(self, site_type=any_site_type):
        result = pan_cancer_analysis(site_type)
        return self.active_driver_gene_ontology(result['profile_against_genes_with_sites'])

    @cases(site_type=site_types)
    def clinvar_active_driver_gene_ontology_with_bg(self, site_type=any_site_type):
        result = clinvar_analysis(site_type)
        return self.active_driver_gene_ontology(result['profile_against_genes_with_sites'])
