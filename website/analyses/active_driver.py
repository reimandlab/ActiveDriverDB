from tempfile import NamedTemporaryFile

import gc
from rpy2.robjects import pandas2ri

from rpy2.robjects.packages import importr
from pandas import read_table, Series
from flask import current_app
from tqdm import tqdm

from exports.protein_data import sites_ac
from imports import MutationImportManager
from models import Gene

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


def active_driver_analysis(mutation_source: str, site_type=None):

    sites = export_and_load(sites_ac)

    if site_type:
        sites = sites[sites['type'].str.contains(site_type)]

    genes_with_sites = sites.gene

    sites = pandas2ri.py2ri(sites)
    gc.collect()

    importer_class = manager.importers[mutation_source]
    importer = importer_class()
    mutations = importer.export_to_df(only_preferred=True)
    mutations = mutations[mutations.gene.isin(genes_with_sites)]
    # TODO: unique? value?
    mutations = pandas2ri.py2ri(mutations)
    gc.collect()

    sequences = series_from_preferred_isoforms('sequence', subset=genes_with_sites)
    sequences = sequences.str.rstrip('*')
    sequences = pandas2ri.py2ri(sequences)

    disorder = series_from_preferred_isoforms('disorder_map', subset=genes_with_sites)
    disorder = pandas2ri.py2ri(disorder)
    gc.collect()

    result = active_driver.ActiveDriver(sequences, disorder, mutations, sites, mc_cores=5)

    return result
