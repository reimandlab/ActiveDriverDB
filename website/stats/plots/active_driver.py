from collections import Counter
from operator import attrgetter
from pathlib import Path
from types import FunctionType
from typing import Mapping

from pandas import Series, DataFrame
from sqlalchemy import func

from analyses import per_cancer_analysis, pan_cancer_analysis, clinvar_analysis
from analyses.enrichment import active_driver_genes_enrichment
from database import db
from helpers.plots import bar_plot, stacked_bar_plot
from models import Mutation, Protein, Gene, Site, MC3Mutation, Cancer, InheritedMutation, MutationSource
from stats.analyses.ontology import Ontology, draw_ontology_graph

from ..store import cases
from .common import site_types_with_any, site_types
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
                Site.types.contains(site_type)
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
    site_type=site_types_with_any,
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


def counts_by(column_name, df: DataFrame, by_unique=False) -> dict:
    if by_unique:
        column = getattr(df, column_name)
        return column.value_counts()
    counts = Counter()
    get_by = attrgetter(column_name)
    for row in df.itertuples():
        counts[get_by(row)] += int(row.count)
    return counts


@cases(site_type=site_types)
@bar_plot
def cancers(site_type):
    result = pan_cancer_analysis(site_type)
    counts = counts_by('cancer_type', result['all_active_mutations'])
    cancer_by_code = {cancer.code: cancer.name for cancer in Cancer.query}

    return (
        counts.keys(),
        counts.values(),
        [
            f'{cancer_by_code[cancer_type]}: {count} mutations'
            for cancer_type, count in counts.items()
        ]
    )


def ontology_plots(
    terms, analysis_name, vector=True, thresholds=(70, 75, 80, 85, 90, 95), allow_misses=True,
    limit_to=None, unflatten=900
):

    predefined_ontologies = {
        'phenotypes': 'data/hp.obo',
        'diseases': 'data/HumanDO.obo',
        'mondo': 'data/mondo.obo'
    }

    ontology_subsets = {
        'mondo': [None, 'disease', 'disease characteristic']
    }

    ontologies = {
        name: Ontology(path)
        for name, path in predefined_ontologies.items()
        if not limit_to or name in limit_to
    }

    path = Path('analyses_output') / 'active_driver_plots' / analysis_name
    path.mkdir(parents=True, exist_ok=True)

    for name, ontology in ontologies.items():
        subsets = ontology_subsets.get(name, [None])
        for subset in subsets:
            for above_percentile in thresholds:
                graph = ontology.process_graph(terms, above_percentile, root_name=subset, allow_misses=allow_misses)
                draw_ontology_graph(
                    graph,
                    path / f'{name}_{above_percentile}{"_" + subset if subset else ""}.{"svg" if vector else "png"}',
                    unflatten
                )


@cases(site_type=site_types)
def cancers_ontology(site_type, vector=False):
    result = pan_cancer_analysis(site_type)
    cancer_by_code = {cancer.code: cancer.name for cancer in Cancer.query}

    mutations = result['all_active_mutations']
    mutations = mutations.assign(cancer_name=Series(
        cancer_by_code[mutation.cancer_type]
        for mutation in mutations.itertuples(index=False)
    ).values)

    terms = counts_by('cancer_name', mutations)

    ontology_plots(
        terms, 'cancers', vector,
        [0, 70, 75, 80, 85, 90, 95],
        allow_misses=False, limit_to=['diseases', 'mondo']
    )


@cases(site_type=site_types)
def diseases_wordcloud(site_type):
    result = clinvar_analysis(site_type.name)
    print(
        'Copy-pase following text into a wordcloud generation program, '
        'e.g. https://www.jasondavies.com/wordcloud/'
    )
    print(' '.join(result['all_active_mutations'].disease))


@cases(site_type=site_types)
def diseases_ontology(site_type, vector=False):
    # NOTE: This is the number of unique mutations, it does not look at the counts!
    result = clinvar_analysis(site_type.name)
    mutations = result['all_active_mutations']
    terms = counts_by('disease', mutations)

    ontology_plots(terms, 'diseases', vector)


@cases(site_type=site_types)
@bar_plot
def cancer_census_enrichment(site_type):
    analyses = {
        'TCGA': pan_cancer_analysis,
        'ClinVar': clinvar_analysis
    }
    results = {}
    p_values = {}
    for name, analysis in analyses.items():
        result = analysis(site_type)
        enrichment, p_value = active_driver_genes_enrichment(result)
        results[name] = enrichment
        p_values[name] = p_value
    return [results.keys(), results.values(), p_values.values()]
