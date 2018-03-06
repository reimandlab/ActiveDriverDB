from collections import defaultdict
from typing import List
from warnings import warn

from numpy import nan
from pandas import DataFrame
from tqdm import tqdm

from analyses.motifs import count_by_active_driver, all_motifs, count_by_sources, MotifsCounter
from analyses.variability_in_population import (
    ptm_variability_population_rare_substitutions,
    does_median_differ_significances,
    proteins_variability_by_ptm_presence,
)
from database import db
from helpers.plots import grouped_box_plot, bar_plot, stacked_bar_plot, p_value_annotations, pie_chart
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

site_types_names = Site.types()
site_types = [SiteType(name=name) for name in site_types_names]
any_site_type = ''


def named(func, name):
    func.__name__ = name
    return func


full_active_driver_analyses = {
    # analysis -> mutation source
    pan_cancer_analysis: MC3Mutation,
    clinvar_analysis: InheritedMutation
}

active_driver_analyses = {
    **full_active_driver_analyses,
    **{
        named(
            lambda site_type: per_cancer_analysis(site_type)[cancer.code], f'per_cancer_analysis_{cancer.code}'
        ): MC3Mutation
        for cancer in Cancer.query
    }
}


class Motif:

    def __init__(self, name, pattern):
        self.name = name
        self.pattern = pattern


def gather_ptm_muts_impacts(source: MutationSource, site_type: SiteType, limit_to_genes: List[str]=None):

    motifs_counter = MotifsCounter(site_type, mode='change_of_motif')
    sites = (
        Site.query.filter(Site.type.contains(site_type))
        .join(Protein).filter(Protein.is_preferred_isoform)
    )

    def fuzzy_site_filter(sites):
        return [
            site for site in sites
            # matches 'O-glycosylation' for site_type 'glycosylation'
            if any(site_type.name in s_t for s_t in site.type)
        ]

    mutations_by_impact_by_gene = {
        # order matters
        'direct': defaultdict(int),
        'motif-changing': defaultdict(int),
        'proximal': defaultdict(int),
        'distal': defaultdict(int)
    }

    mutations = (
        Mutation.query
        .filter(Mutation.in_sources(source))
        .join(Protein)
        .join(Gene, Gene.preferred_isoform_id == Protein.id)
    )
    motifs_data = motifs_counter.gather_muts_and_sites(mutations, sites, occurrences_in=[source])

    all_breaking_muts = set()
    for motif_name, breaking_muts in motifs_data.muts_breaking_sites_motif.items():
        all_breaking_muts.update(breaking_muts)

    mutations = mutations.filter(Mutation.affected_sites.any(Site.type.contains(site_type)))
    if limit_to_genes is not None:
        mutations = mutations.filter(
            Gene.name.in_(limit_to_genes)
        )
    mutations = mutations.with_entities(Gene, Mutation)

    for gene, mutation in tqdm(mutations, total=mutations.count()):

        impact = mutation.impact_on_ptm(fuzzy_site_filter)
        if impact != 'direct' and mutation in all_breaking_muts:
            mutations_by_impact_by_gene['motif-changing'][gene] += 1
            continue
        assert impact != 'none'
        mutations_by_impact_by_gene[impact][gene] += 1

    return mutations_by_impact_by_gene


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
        return self.most_mutated_sites([MC3Mutation], site_type)

    @cases(site_type=site_types_names)
    @counter
    def most_mutated_sites_clinvar(self, site_type=any_site_type):
        return self.most_mutated_sites([InheritedMutation], site_type)

    both_sources_cases = cases(
        site_type=site_types_names + [any_site_type],
        intersection=[True, False]
    ).set_mode('product')

    @both_sources_cases
    def most_mutated_sites_mc3_and_clinvar(self, site_type, intersection):
        return self.most_mutated_sites(
            [MC3Mutation, InheritedMutation],
            site_type,
            intersection
        )

    @staticmethod
    @bar_plot
    def most_mutated_sites(sources, site_type=any_site_type, intersection=None):
        from analyses.enrichment import most_mutated_sites

        sites, counts = zip(*most_mutated_sites(
            sources, site_type, limit=20, muts_intersection=intersection
        ).all())

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
        return (
            top_fdr.gene,
            mutation_counts,
            [f'Mutations: {count}<br>FDR: {fdr}' for count, fdr in zip(mutation_counts, top_fdr.fdr)]
        )

    @staticmethod
    def active_driver_by_muts_stacked(result, source, site_type):
        top_fdr = result['top_fdr']
        grouped = gather_ptm_muts_impacts(source, site_type, limit_to_genes=top_fdr.gene)
        return {
            impact: ([gene.name for gene in muts_by_gene], muts_by_gene.values(), [])
            for impact, muts_by_gene in grouped.items()
        }

    active_driver_cases = cases(
        analysis=full_active_driver_analyses,
        site_type=site_types + [SiteType(name=any_site_type)],
    ).set_mode('product')

    @active_driver_cases
    @counter
    @stacked_bar_plot
    def active_driver_muts_by_impact(self, analysis, site_type):
        source = active_driver_analyses[analysis]
        result = analysis(site_type.name)
        return self.active_driver_by_muts_stacked(result, source, site_type)

    @active_driver_cases
    @counter
    @bar_plot
    def active_driver_muts(self, analysis, site_type):
        source = active_driver_analyses[analysis]
        result = analysis(site_type.name)
        return self.active_driver_by_muts_count(result, source, site_type)

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

        ratio_and_count = {}
        for gene_name, counts in counts_by_gene.items():
            by_count = sum(getattr(counts, by).values())
            bg_count = sum(getattr(counts, bg).values())
            if by_count:
                ratio_and_count[gene_name] = (by_count / bg_count, by_count)

        genes_ordered = sorted(ratio_and_count, key=ratio_and_count.get, reverse=True)
        return genes_ordered

    def prepare_motifs_plot(self, counts_by_gene, site_type: SiteType, y_axis: str):

        # order by percentage
        genes_ordered = self.genes_by_ratio(counts_by_gene, y_axis)

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

                broken_sites = counts.sites_with_broken_motif[motif]
                motif_sites = counts.sites_with_motif[motif]
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
        if len(sources) > 1:
            kwargs['intersection'] = sources
        counts_by_gene = count_by_sources(sources, site_type, by_genes=True, **kwargs)

        return self.prepare_motifs_plot(counts_by_gene, site_type, y_axis)

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

    def calc_motifs_in_active_driver(self, analysis, site_type, count_method: str, y_axis: str):
        analysis_result = analysis(site_type.name)
        source = active_driver_analyses[analysis]

        kwargs = {}
        if count_method == 'occurrences':
            kwargs['occurrences_in'] = [source]

        counts_by_gene = count_by_active_driver(site_type, source, analysis_result, by_genes=True, **kwargs)

        return self.prepare_motifs_plot(counts_by_gene, site_type, y_axis)

    @analysis_cases
    @stacked_bar_plot
    def muts_breaking_motifs_in_active_driver(self, analysis, site_type: SiteType, count_method: str):
        return self.calc_motifs_in_active_driver(analysis, site_type, count_method, 'mutations')

    @analysis_cases
    @stacked_bar_plot
    def broken_motifs_in_active_driver(self, analysis, site_type: SiteType, count_method: str):
        return self.calc_motifs_in_active_driver(analysis, site_type, count_method, 'sites')

    @cases(only_preferred=[True, False])
    @bar_plot
    def sites_in_disordered_regions(self, only_preferred):
        disordered = defaultdict(int)
        not_disordered = defaultdict(int)

        query = Site.query
        if only_preferred:
            query = query.join(Protein).filter(Protein.is_preferred_isoform)

        for site in tqdm(query.all()):
            for site_type in site.type:
                try:
                    if site.protein.disorder_map[site.position - 1] == '1':
                        disordered[site_type] += 1
                    else:
                        not_disordered[site_type] += 1
                except IndexError:
                    warn(f"Disorder of {site.protein} does not include {site.position}")

        values = [
            100 * disordered[site_type] / (disordered[site_type] + not_disordered[site_type])
            for site_type in site_types_names
        ]

        return site_types_names, values

    @cases(only_preferred=[True, False])
    @bar_plot
    def sites_counts(self, only_preferred):
        counts = defaultdict(int)

        query = Site.query
        if only_preferred:
            query = query.join(Protein).filter(Protein.is_preferred_isoform)

        for site in tqdm(query.all()):
            for site_type in site.type:
                counts[site_type] += 1

        return site_types_names, [counts[site_type] for site_type in site_types_names]

    impact_cases = cases(source=[InheritedMutation, MC3Mutation], site_type=site_types).set_mode('product')

    @impact_cases
    @pie_chart
    def ptm_mutations_by_impact(self, source: MutationSource, site_type: SiteType):

        muts_by_impact_by_gene = gather_ptm_muts_impacts(source, site_type)
        muts_by_impact = {
            impact: sum(gene_muts.values())
            for impact, gene_muts in muts_by_impact_by_gene.items()
        }

        return {source.name: muts_by_impact}
