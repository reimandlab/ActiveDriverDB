from typing import Mapping, Iterable, List

from numpy import percentile, nan
from pandas import DataFrame

from analyses.motifs import count_by_active_driver, all_motifs, count_by_sources
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
    SiteType,
    MutationSource,
)
from analyses.active_driver import pan_cancer_analysis, per_cancer_analysis, clinvar_analysis
from .store import CountStore, counter, cases


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
bar_plot = as_decorator(bar_plot, unpack=True)
stacked_bar_plot = as_decorator(stacked_bar_plot)


site_types_names = Site.types()
site_types = [SiteType(name=name) for name in site_types_names]
any_site_type = ''


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


def named(func, name):
    func.__name__ = name
    return func


active_driver_analyses = {
    # analysis -> mutation source
    pan_cancer_analysis: MC3Mutation,
    clinvar_analysis: InheritedMutation,
    **{
        named(lambda site_type: per_cancer_analysis(site_type)[cancer.code], f'per_cancer_analysis_{cancer.code}'): MC3Mutation
        for cancer in Cancer.query
    }
}


class Motif:

    def __init__(self, name, pattern):
        self.name = name
        self.pattern = pattern


class Plots(CountStore):

    storage_model = Plot

    @cases(site_type=site_types_names)
    @counter
    @grouped_box_plot
    def ptm_variability_population_rare_substitutions(self, site_type=any_site_type):
        return ptm_variability_population_rare_substitutions(site_type)

    @cases(site_type=site_types_names)
    @counter
    def ptm_variability_population_rare_substitutions_significance(self, site_type=any_site_type):
        results = ptm_variability_population_rare_substitutions(site_type)
        significances = does_median_differ_significances(results, paired=True)
        return p_value_annotations(results, significances)

    motifs = [
        Motif(pattern='.{7}N[^P][STCV].{5}', name='n_linked'),
        Motif(pattern='.{7}(TAPP|TSAPP|TV.P|[ST].P).{4}', name='o_linked'),
        Motif(pattern='(.{7}W..W.{4}|.{4}W..W.{7}|.{7}W[ST].C.{4})', name='c_linked')
    ]

    @cases(motif=motifs)
    @grouped_box_plot
    def ptm_variability_population_rare_substitutions_glycosylation(self, motif):
        return ptm_variability_population_rare_substitutions('glycosylation', motif.pattern)

    @cases(motif=motifs)
    @grouped_box_plot
    def ptm_variability_population_rare_substitutions_significance_glycosylation(self, motif):
        results = ptm_variability_population_rare_substitutions('glycosylation', motif.pattern)
        significances = does_median_differ_significances(results, paired=True)
        return p_value_annotations(results, significances)

    #
    # PROTEINS VARIABILITY
    #

    variability_cases = cases(site_type=site_types_names + [any_site_type], by_counts=[None, True]).set_mode('product')

    @variability_cases
    @grouped_box_plot
    def proteins_variability_by_ptm_presence(self, site_type, by_counts):
        return proteins_variability_by_ptm_presence(site_type, by_counts)

    glycosylation_motifs_cases = cases(by_counts=[None, True], motif=motifs).set_mode('product')

    @glycosylation_motifs_cases
    @grouped_box_plot
    def proteins_variability_by_ptm_presence_glycosylation(self, by_counts, motif):
        return proteins_variability_by_ptm_presence('glycosylation', by_counts, motif.pattern)

    @variability_cases
    def proteins_variability_by_ptm_presence_significance(self, site_type, by_counts):
        results = proteins_variability_by_ptm_presence(site_type, by_counts)
        significances = does_median_differ_significances(results)
        return p_value_annotations(results, significances)

    @glycosylation_motifs_cases
    def proteins_variability_by_ptm_presence_significance_glycosylation(self, by_counts, motif):
        results = proteins_variability_by_ptm_presence('glycosylation', by_counts, motif.pattern)
        significances = does_median_differ_significances(results)
        return p_value_annotations(results, significances)

    #
    # MUTATED SITES
    #

    @cases(site_type=site_types_names)
    @counter
    def most_mutated_sites_mc3(self, site_type=any_site_type):
        return self.most_mutated_sites(MC3Mutation, site_type)

    @cases(site_type=site_types_names)
    @counter
    def most_mutated_sites_clinvar(self, site_type=any_site_type):
        return self.most_mutated_sites(InheritedMutation, site_type)

    @staticmethod
    @bar_plot
    def most_mutated_sites(source, site_type=any_site_type):
        from analyses.enrichment import most_mutated_sites

        sites, counts = zip(*most_mutated_sites(source, site_type, limit=20).all())

        return [f'{site.protein.gene_name} {site.position}{site.residue}' for site in sites], counts

    #
    # ACTIVE DRIVER
    #

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
        return top_fdr.gene, mutation_counts, [f'Mutations: {count}<br>FDR: {fdr}' for count, fdr in zip(top_fdr.fdr)]

    @cases(site_type=site_types_names)
    @counter
    @bar_plot
    def pan_cancer_active_driver(self, site_type=any_site_type):
        result = pan_cancer_analysis(site_type)
        return self.active_driver_by_muts_count(result, MC3Mutation, site_type)

    @cases(site_type=site_types_names)
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

    #
    # GENE ONTOLOGY
    #

    @staticmethod
    @bar_plot
    def active_driver_gene_ontology(profile: DataFrame):
        if profile.empty:
            return [], []
        return profile['t name'], profile['Q&T'], [
            f'Q&T: {qt}<br>P-value: {p}'
            for qt, p in zip(profile['Q&T'], profile['p-value'])
        ]

    @cases(site_type=site_types_names)
    @counter
    def pan_cancer_active_driver_gene_ontology(self, site_type=any_site_type):
        result = pan_cancer_analysis(site_type)
        return self.active_driver_gene_ontology(result['profile'])

    @cases(site_type=site_types_names)
    @counter
    def clinvar_active_driver_gene_ontology(self, site_type=any_site_type):
        result = clinvar_analysis(site_type)
        return self.active_driver_gene_ontology(result['profile'])

    @cases(site_type=site_types_names)
    def pan_cancer_active_driver_gene_ontology_with_bg(self, site_type=any_site_type):
        result = pan_cancer_analysis(site_type)
        return self.active_driver_gene_ontology(result['profile_against_genes_with_sites'])

    @cases(site_type=site_types_names)
    def clinvar_active_driver_gene_ontology_with_bg(self, site_type=any_site_type):
        result = clinvar_analysis(site_type)
        return self.active_driver_gene_ontology(result['profile_against_genes_with_sites'])

    #
    # MOTIFS
    #

    @staticmethod
    def genes_by_ratio(counts_by_gene, y_axis):

        assert y_axis in ['sites', 'mutations']

        if y_axis == 'sites':
            by, bg = 'sites_with_broken_motif', 'sites_with_motif'
        else:
            by, bg = 'muts_breaking_sites_motif', 'muts_around_sites_with_motif'

        def sum_or_count(data):
            try:
                return sum(data)
            except TypeError:
                return sum(len(e) for e in data)

        ratio_and_count = {}
        for gene_name, counts in counts_by_gene.items():
            by_count = sum_or_count(getattr(counts, by).values())
            bg_count = sum_or_count(getattr(counts, bg).values())
            if by_count:
                ratio_and_count[gene_name] = (by_count / bg_count, by_count)

        genes_ordered = sorted(ratio_and_count, key=ratio_and_count.get, reverse=True)
        return genes_ordered

    @staticmethod
    def prepare_motifs_plot(counts_by_gene, genes_ordered, site_type: SiteType, y_axis='mutations'):

        # bars = genes, stacks = motifs
        data = {}

        for motif in all_motifs[site_type.name].keys():

            y = []
            comments = []

            for gene_name in genes_ordered:
                counts = counts_by_gene[gene_name]

                breaking_muts = counts.muts_breaking_sites_motif[motif]
                muts_around = counts.muts_around_sites_with_motif[motif]
                muts_percentage = breaking_muts / muts_around * 100 if muts_around else nan

                broken_sites = len(counts.sites_with_broken_motif[motif])
                motif_sites = len(counts.sites_with_motif[motif])
                sites_percentage = broken_sites / motif_sites * 100 if motif_sites else nan

                if y_axis == 'mutations':
                    y.append(breaking_muts or None)
                elif y_axis == 'sites':
                    y.append(broken_sites or None)
                else:
                    ValueError('Unknown y-axis value')

                comments.append(
                    f'{breaking_muts} mutations breaking this motif '
                    f'({muts_percentage:.2f}% of PTM muts close to that motif).'
                    f'<br>'
                    f'{broken_sites} sites with broken motif ({sites_percentage:.2f}% of sites with this motif).'
                    if broken_sites else None
                )

            data[motif] = genes_ordered, y, comments
        return data

    motifs_cases = cases(
        site_type=[SiteType(name='glycosylation')],
        sources=[[InheritedMutation], [MC3Mutation], [InheritedMutation, MC3Mutation]],
        count_method=['occurrences', 'distinct']
    ).set_mode('product')

    def calc_motifs(self, sources, site_type, count_method, y_axis: str):
        kwargs = {}
        if count_method == 'occurrences':
            kwargs['occurrences_in'] = sources
        counts_by_gene = count_by_sources(sources, site_type, by_genes=True, **kwargs)
        genes_ordered = self.genes_by_ratio(counts_by_gene, y_axis)
        return self.prepare_motifs_plot(counts_by_gene, genes_ordered, site_type)

    @motifs_cases
    @stacked_bar_plot
    def muts_breaking_motifs(self, sources: List[MutationSource], site_type: SiteType, count_method: str):
        return self.calc_motifs(sources, site_type, count_method, 'mutations')

    @motifs_cases
    @stacked_bar_plot
    def broken_motifs(self, sources: List[MutationSource], site_type: SiteType, count_method: str):
        return self.calc_motifs(sources, site_type, count_method, 'sites')

    analysis_cases = cases(
        site_type=[SiteType(name='glycosylation')],
        analysis=active_driver_analyses,
        count_method=['occurrences', 'distinct']
    ).set_mode('product')

    def calc_motifs_in_active_driver(self, analysis, site_type, count_method: str, y_axis: str, mode='broken_motif'):
        analysis_result = analysis(site_type.name)
        source = active_driver_analyses[analysis]

        kwargs = {}
        if count_method == 'occurrences':
            kwargs['occurrences_in'] = [source]

        counts_by_gene = count_by_active_driver(site_type, source, analysis_result, by_genes=True, mode=mode, **kwargs)

        # order by percentage
        genes_ordered = self.genes_by_ratio(counts_by_gene, y_axis)

        return self.prepare_motifs_plot(counts_by_gene, genes_ordered, site_type, y_axis=y_axis)

    @analysis_cases
    @stacked_bar_plot
    def muts_breaking_motifs_in_active_driver(self, analysis, site_type: SiteType, count_method: str):
        return self.calc_motifs_in_active_driver(analysis, site_type, count_method, 'mutations')

    @analysis_cases
    @stacked_bar_plot
    def broken_motifs_in_active_driver(self, analysis, site_type: SiteType, count_method: str):
        return self.calc_motifs_in_active_driver(analysis, site_type, count_method, 'sites')
