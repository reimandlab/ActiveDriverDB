from types import FunctionType
from typing import Mapping

from sqlalchemy import func

from analyses import per_cancer_analysis, pan_cancer_analysis, clinvar_analysis
from database import db
from helpers.plots import bar_plot, stacked_bar_plot
from models import Mutation, Protein, Gene, Site, MC3Mutation, Cancer, InheritedMutation, SiteType, MutationSource

from ..store import cases
from .common import site_types, any_site_type
from .ptm_mutations import gather_ptm_muts_impacts


def subset_analysis_as_function_of_site(analyses_collection, key, name):

    def analysis(site_type):
        return analyses_collection(site_type)[key]

    analysis.__name__ = name

    return analysis


Analysis = FunctionType

whole_dataset_analyses: Mapping[Analysis, MutationSource] = {
    pan_cancer_analysis: MC3Mutation,
    clinvar_analysis: InheritedMutation
}

subset_analyses = {
    subset_analysis_as_function_of_site(
        per_cancer_analysis,
        cancer.code,
        f'per_cancer_analysis_{cancer.code}'
    ): MC3Mutation
    for cancer in Cancer.query
}

all_analyses = {
    **whole_dataset_analyses,
    **subset_analyses
}


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


def by_muts_count(result, source: MutationSource, site_type, filters=None):
    top_fdr = result['top_fdr']
    mutation_counts = count_mutations_by_gene(source, top_fdr.gene, site_type, filters)
    return (
        top_fdr.gene,
        mutation_counts,
        [f'Mutations: {count}<br>FDR: {fdr}' for count, fdr in zip(mutation_counts, top_fdr.fdr)]
    )


def by_muts_stacked(result, source, site_type):
    top_fdr = result['top_fdr']
    genes = top_fdr.gene
    grouped = gather_ptm_muts_impacts(source, site_type, limit_to_genes=genes)
    return {
        impact: (genes, [muts_by_gene[gene_name] for gene_name in genes], [])
        for impact, muts_by_gene in grouped.items()
    }


active_driver_cases = cases(
    analysis=whole_dataset_analyses,
    site_type=site_types + [SiteType(name=any_site_type)],
).set_mode('product')


@active_driver_cases
@stacked_bar_plot
def muts_by_impact(analysis, site_type):
    source = all_analyses[analysis]
    result = analysis(site_type.name)
    return by_muts_stacked(result, source, site_type)


@active_driver_cases
@bar_plot
def muts(analysis, site_type):
    source = all_analyses[analysis]
    result = analysis(site_type.name)
    return by_muts_count(result, source, site_type)


@cases(cancer_code={cancer.code for cancer in Cancer.query})
@bar_plot
def per_cancer_glycosylation(cancer_code, site_type='glycosylation'):
    results = per_cancer_analysis(site_type)
    try:
        result = results[cancer_code]
    except KeyError:
        print(f'No results for {cancer_code}')
        return [], []
    return by_muts_count(result, MC3Mutation, site_type, MC3Mutation.cancer_code == cancer_code)
