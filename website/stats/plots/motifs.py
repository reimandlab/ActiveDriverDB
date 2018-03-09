from collections import defaultdict
from typing import List

from numpy import nan

from analyses.motifs import count_by_active_driver, all_motifs, count_by_sources, motifs_hierarchy
from helpers.plots import stacked_bar_plot, bar_plot
from models import (
    MC3Mutation, InheritedMutation,
    SiteType,
    MutationSource,
    source_manager,
)

from ..store import cases
from .active_driver import all_analyses


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


def prepare_motifs_plot(counts_by_gene, site_type: SiteType, y_axis: str):

    # order by percentage
    genes_ordered = genes_by_ratio(counts_by_gene, y_axis)

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


def calc_motifs(sources, site_type, count_method, y_axis: str):
    kwargs = {}
    if count_method == 'occurrences':
        kwargs['occurrences_in'] = sources
    if len(sources) > 1:
        kwargs['intersection'] = sources
    counts_by_gene = count_by_sources(sources, site_type, by_genes=True, **kwargs)

    return prepare_motifs_plot(counts_by_gene, site_type, y_axis)


@motifs_cases
@stacked_bar_plot
def muts_breaking(sources: List[MutationSource], site_type: SiteType, count_method: str):
    return calc_motifs(sources, site_type, count_method, 'mutations')


@motifs_cases
@stacked_bar_plot
def broken(sources: List[MutationSource], site_type: SiteType, count_method: str):
    return calc_motifs(sources, site_type, count_method, 'sites')


@cases(site_type=[SiteType(name='glycosylation')])
@stacked_bar_plot
def all(site_type: SiteType):
    counts = count_by_sources(source_manager.confirmed, site_type, by_genes=False)

    motifs = defaultdict(dict)
    for motif_group, members in motifs_hierarchy[site_type.name].items():

        for motif in members:
            count = counts.sites_with_motif[motif]
            motifs[motif][motif_group] = count

    return {
        motif: (group_counts.keys(), group_counts.values())
        for motif, group_counts in motifs.items()
    }


analysis_cases = cases(
    site_type=[SiteType(name='glycosylation')],
    analysis=all_analyses,
    count_method=['occurrences', 'distinct']
).set_mode('product')


def calc_motifs_in_active_driver(analysis, site_type, count_method: str, y_axis: str):
    analysis_result = analysis(site_type.name)
    source = all_analyses[analysis]

    kwargs = {}
    if count_method == 'occurrences':
        kwargs['occurrences_in'] = [source]

    counts_by_gene = count_by_active_driver(site_type, source, analysis_result, by_genes=True, **kwargs)

    return prepare_motifs_plot(counts_by_gene, site_type, y_axis)


@analysis_cases
@stacked_bar_plot
def muts_breaking_in_active_driver(analysis, site_type: SiteType, count_method: str):
    return calc_motifs_in_active_driver(analysis, site_type, count_method, 'mutations')


@analysis_cases
@stacked_bar_plot
def broken_in_active_driver(analysis, site_type: SiteType, count_method: str):
    return calc_motifs_in_active_driver(analysis, site_type, count_method, 'sites')
