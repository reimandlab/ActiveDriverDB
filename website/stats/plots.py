from typing import Mapping, Iterable

from numpy import percentile
from pandas import DataFrame

from analyses.variability_in_population import (
    ptm_variability_population_rare_substitutions,
    does_median_differ_significances,
    proteins_variability_by_ptm_presence,
)
from database import db
from models import (
    Plot, Site, MC3Mutation, InheritedMutation, Cancer,
    Gene,
    Protein,
    Mutation,
    func,
)
from analyses.active_driver import pan_cancer_analysis, per_cancer_analysis, clinvar_analysis
from .store import CountStore, counter, cases


def bar_plot(labels: Iterable, values: Iterable, text: Iterable=None):
    data = {
        'x': list(labels),
        'y': list(values),
        'type': 'bar'
    }
    if text:
        data['text'] = list(text)
    return [data]


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


def as_decorator(plotting_func, unpack=False):
    def decorator(data_func):

        def data_func_with_plot(*args, **kwargs):
            data = data_func(*args, **kwargs)
            if unpack:
                return plotting_func(*data)
            else:
                return plotting_func(data)

        return data_func_with_plot
    return decorator


grouped_box_plot = as_decorator(grouped_box_plot)
bar_plot = as_decorator(bar_plot, unpack=True)


site_types = Site.types()
any_site_type = ''


def p_value_annotations(results, significances):
    return [
        {
            'x': 1 * i,
            'y': max(percentile(result[population_source], 75) for result in results.values()) + 10,
            'xref': 'x',
            'yref': 'y',
            'text': f'p-value: {significance:.3f}',
            'showarrow': False
        }
        for i, (population_source, significance) in enumerate(significances.items())
    ]


class Plots(CountStore):

    storage_model = Plot

    @cases(site_type=Site.types())
    @counter
    @grouped_box_plot
    def ptm_variability_population_rare_substitutions(self, site_type=any_site_type):
        results = ptm_variability_population_rare_substitutions(site_type)
        return results

    @cases(site_type=Site.types())
    @counter
    def ptm_variability_population_rare_substitutions_significance(self, site_type=any_site_type):
        results = ptm_variability_population_rare_substitutions(site_type)
        significances = does_median_differ_significances(results)
        return p_value_annotations(results, significances)

    @cases(site_type=Site.types(), by_counts=[True])
    @counter
    @grouped_box_plot
    def proteins_variability_by_ptm_presence(self, site_type=any_site_type, by_counts=False):
        results = proteins_variability_by_ptm_presence(site_type, by_counts)
        return results

    @cases(site_type=Site.types())
    @counter
    def proteins_variability_by_ptm_presence_significance(self, site_type=any_site_type):
        results = proteins_variability_by_ptm_presence(site_type)
        significances = does_median_differ_significances(results)
        return p_value_annotations(results, significances)

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
    def count_mutations_by_gene(source, genes, site_type, filters=None):
        counts = []
        for gene in genes:
            query = (
                db.session.query(func.sum(source.count))
                .select_from(source)
                .join(Mutation).join(Protein)
                .filter(Mutation.affected_sites.any(
                    Site.type.contains(site_type)
                ))
                .join(Gene, Gene.preferred_isoform_id == Protein.id)
                .filter(Gene.name == gene)
            )
            if filters is not None:
                query = query.filter(filters)
            counts.append(query.scalar())
        return counts

    def active_driver_by_muts_count(self, result, source, site_type, filters=None):
        top_fdr = result['top_fdr']
        mutation_counts = self.count_mutations_by_gene(source, top_fdr.gene, site_type, filters)
        return top_fdr.gene, mutation_counts, [f'fdr: {fdr}' for fdr in top_fdr.fdr]

    @cases(site_type=site_types)
    @counter
    @bar_plot
    def pan_cancer_active_driver(self, site_type=any_site_type):
        result = pan_cancer_analysis(site_type)
        return self.active_driver_by_muts_count(result, MC3Mutation, site_type)

    @cases(site_type=site_types)
    @counter
    @bar_plot
    def clinvar_active_driver(self, site_type=any_site_type):
        result = clinvar_analysis(site_type)
        return self.active_driver_by_muts_count(result, InheritedMutation, site_type)

    @cases(cancer_code={cancer.code for cancer in Cancer.query})
    @bar_plot
    def per_cancer_active_driver_glycosylation(self, cancer_code, site_type='glycosylation'):
        results = per_cancer_analysis(site_type)
        try:
            result = results[cancer_code]
        except KeyError:
            print(f'No results for {cancer_code}')
            return [], []
        return self.active_driver_by_muts_count(result, MC3Mutation, site_type, MC3Mutation.cancer_code == cancer_code)

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
