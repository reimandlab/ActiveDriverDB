from tempfile import NamedTemporaryFile

import gc
from traceback import print_exc

from diskcache import Cache
from rpy2.rinterface._rinterface import RRuntimeError
from rpy2.robjects import pandas2ri, r
from rpy2.robjects.packages import importr
from pandas import read_table, Series
from flask import current_app
from tqdm import tqdm

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


def run_active_driver(sequences, disorder, mutations, sites, mc_cores=4, progress_bar=True, **kwargs):

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


def per_cancer_analysis(site_type):

    sequences, disorder, all_mutations, sites = cached_active_driver_data('mc3', site_type)

    results = {}

    for cancer_type in all_mutations.cancer_type.unique():
        mutations = all_mutations[all_mutations.cancer_type == cancer_type]
        results[cancer_type] = run_active_driver(sequences, disorder, mutations, sites)

    return results


def pan_cancer_analysis(site_type):

    sequences, disorder, mutations, sites = cached_active_driver_data('mc3', site_type)
    return run_active_driver(sequences, disorder, mutations, sites)
