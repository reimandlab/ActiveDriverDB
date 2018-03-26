from pandas import DataFrame

from analyses import pan_cancer_analysis, clinvar_analysis
from helpers.plots import bar_plot

from ..store import cases, counter
from .common import site_types, any_site_type


@bar_plot
def active_driver_gene_ontology(profile: DataFrame):
    if profile.empty:
        return [], []
    return profile['t name'], profile['Q&T'], [
        f'Q&T: {qt}<br>P-value: {p}'
        for qt, p in zip(profile['Q&T'], profile['p-value'])
    ]


@cases(site_type=site_types)
@counter
def pan_cancer_active_driver(site_type=any_site_type):
    result = pan_cancer_analysis(site_type.name)
    return active_driver_gene_ontology(result['profile'])


@cases(site_type=site_types)
@counter
def clinvar_active_driver(site_type=any_site_type):
    result = clinvar_analysis(site_type.name)
    return active_driver_gene_ontology(result['profile'])


@cases(site_type=site_types)
def pan_cancer_active_driver_with_bg(site_type=any_site_type):
    result = pan_cancer_analysis(site_type.name)
    return active_driver_gene_ontology(result['profile_against_genes_with_sites'])


@cases(site_type=site_types)
def clinvar_active_driver_with_bg(site_type=any_site_type):
    result = clinvar_analysis(site_type.name)
    return active_driver_gene_ontology(result['profile_against_genes_with_sites'])
