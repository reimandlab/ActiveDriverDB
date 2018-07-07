from datetime import datetime
from os import cpu_count
from pathlib import Path
from tempfile import NamedTemporaryFile

import gc
from traceback import print_exc

from diskcache import Cache
from rpy2.rinterface._rinterface import RRuntimeError
from rpy2.robjects import pandas2ri, r
from rpy2.robjects.packages import importr
from pandas import read_table, Series, DataFrame
from flask import current_app
from tqdm import tqdm
from gprofiler import GProfiler

from exports.protein_data import sites_ac
from imports import MutationImportManager
from models import Gene


USE_LOCAL_AD = True


if USE_LOCAL_AD:
    r.source("ActiveDriver/R/ActiveDriver.R")
    # ActiveDriver is in the global namespace now
    active_driver = r
else:
    active_driver = importr("ActiveDriver")


def get_date() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d_%H%-M%-S")


def export_and_load(exporter, *args, compression=None, **kwargs):
    with current_app.app_context():
        with NamedTemporaryFile() as file:
            exporter(*args, path=file.name, **kwargs)
            return read_table(file.name, compression=compression)


def series_from_preferred_isoforms(trait, subset=None):

    sequences = []
    names = []
    for gene in tqdm(Gene.query.all()):
        if not gene.preferred_isoform:
            continue
        sequence = getattr(gene.preferred_isoform, trait)
        sequences.append(sequence)
        names.append(gene.name)

    series = Series(sequences, names)

    if subset is not None:
        series = series[series.index.isin(subset)]

    return series


manager = MutationImportManager()


cache = Cache('active_driver_data')


def prepare_active_driver_data(mutation_source: str, site_type=None):

    sites = export_and_load(sites_ac)

    if site_type:
        sites = sites[sites['type'].str.contains(site_type)]

    genes_with_sites = sites.gene
    gc.collect()

    importer_class = manager.importers[mutation_source]
    importer = importer_class()
    mutations = importer.export_to_df(only_preferred=True)
    mutations = mutations[mutations.gene.isin(genes_with_sites)]
    gc.collect()

    sequences = series_from_preferred_isoforms('sequence', subset=genes_with_sites)
    sequences = sequences.str.rstrip('*')

    disorder = series_from_preferred_isoforms('disorder_map', subset=genes_with_sites)
    gc.collect()

    return sequences, disorder, mutations, sites


def cached_active_driver_data(*args):

    if args not in cache:
        cache[args] = prepare_active_driver_data(*args)

    return cache[args]


def run_active_driver(sequences, disorder, mutations, sites, mc_cores=None, progress_bar=True, **kwargs):

    if not mc_cores:
        mc_cores = cpu_count()

    arguments = [
        pandas2ri.py2ri(python_object)
        for python_object in [sequences, disorder, mutations, sites]
    ]

    try:
        result = active_driver.ActiveDriver(
            *arguments, mc_cores=mc_cores, progress_bar=progress_bar, **kwargs
        )
        if result:
            return {k: pandas2ri.ri2py(v) for k, v in result.items()}
    except RRuntimeError as e:
        print_exc()
        return e


def profile_genes_with_active_sites(enriched_genes, background=None) -> DataFrame:

    if len(enriched_genes) == 0:
        return DataFrame()

    gp = GProfiler('ActiveDriverDB', want_header=True)

    response = gp.gprofile(enriched_genes, custom_bg=background)

    if not response:
        return DataFrame()

    header, *rows = response

    return DataFrame(rows, columns=header)


def process_result(result, sites, fdr_cutoff=0.05):

    if not result:
        return

    all_genes = sites.gene.unique()

    enriched = result['all_gene_based_fdr']
    enriched = enriched[enriched.fdr < fdr_cutoff]
    enriched = enriched.sort_values('fdr')

    enriched_genes = enriched.gene.unique()

    result['profile'] = profile_genes_with_active_sites(enriched_genes)
    result['profile_against_genes_with_sites'] = profile_genes_with_active_sites(enriched_genes, all_genes)
    result['top_fdr'] = enriched

    return result


def save_all(analysis_name: str, data, base_path=None):
    if base_path:
        path = base_path / analysis_name
    else:
        base_path = Path('analyses_output')
        path = base_path / analysis_name / get_date()

    # create what's needed
    path.mkdir(parents=True, exist_ok=True)

    for name, datum in data.items():

        # deal with the nested case
        if isinstance(datum, dict):
            save_all(name, datum, base_path=path)
            continue

        # save to tsv file
        datum.to_csv(path / f'{name}.tsv', sep='\t')


def per_cancer_analysis(site_type):

    sequences, disorder, all_mutations, sites = cached_active_driver_data('mc3', site_type)

    results = {}

    for cancer_type in all_mutations.cancer_type.unique():
        mutations = all_mutations[all_mutations.cancer_type == cancer_type]
        result = run_active_driver(sequences, disorder, mutations, sites)
        results[cancer_type] = process_result(result, sites)

    save_all(f'pan_cancer-{site_type}', results)

    return results


def source_specific_analysis(mutations_source, site_type):

    sequences, disorder, mutations, sites = cached_active_driver_data(mutations_source, site_type)
    result = run_active_driver(sequences, disorder, mutations, sites)
    result = process_result(result, sites)

    save_all(f'{mutations_source}-{site_type}', result)

    return result


def pan_cancer_analysis(site_type):
    return source_specific_analysis('mc3', site_type)


def clinvar_analysis(site_type):
    return source_specific_analysis('clinvar', site_type)
