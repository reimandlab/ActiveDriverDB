import os
from collections import OrderedDict

from tqdm import tqdm

from database import fast_count, yield_objects
from models import Gene, InheritedMutation, MC3Mutation, ExomeSequencingMutation, The1000GenomesMutation
from models import Site
from models import Protein
from helpers.commands import register_decorator


EXPORTERS = OrderedDict()
exporter = register_decorator(EXPORTERS)


def create_path_if_possible(path):
    """Create all directories on way to the file specified in given path.
    Does not raise any errors if the path already exists."""
    return os.makedirs(os.path.dirname(path), exist_ok=True)


def file_exporter(default_path):
    def export_wrapper(func):
        def executable(*args, path=default_path, **kwargs):

            create_path_if_possible(path)

            with open(path, 'w') as f:
                func(f, *args, **kwargs)
                return path
        executable.__name__ = func.__name__

        return exporter(executable)
    return export_wrapper


@file_exporter(default_path='exported/primary_isoforms.tsv')
def primary_isoforms(f):
    """A list of primary isoforms of all genes in the database."""

    for gene in tqdm(Gene.query.filter(Gene.preferred_isoform).all()):
        f.write(gene.name + '\t' + gene.preferred_isoform.refseq + '\n')


@file_exporter(default_path='exported/preferred_isoforms_sequences.fa')
def sequences_ac(f):
    """Sequences as needed for Active Driver input.
    Includes only data from primary (preferred) isoforms."""

    for gene in tqdm(Gene.query.all()):
        if not gene.preferred_isoform:
            continue
        f.write('>' + gene.name + '\n')
        f.write(gene.preferred_isoform.sequence + '\n')


@file_exporter(default_path='exported/preferred_isoforms_disorder.fa')
def disorder_ac(f):
    """Disorder data as needed for Active Driver input.
    Includes only data from primary (preferred) isoforms."""

    for gene in tqdm(Gene.query.all()):
        if not gene.preferred_isoform:
            continue
        f.write('>' + gene.name + '\n')
        f.write(gene.preferred_isoform.disorder_map + '\n')


@file_exporter(default_path='exported/sites.tsv')
def sites_ac(f):
    """Sites as needed for Active Driver input.
    Includes only data from primary (preferred) isoforms."""
    header = ['gene', 'position', 'residue', 'type', 'kinase', 'pmid']

    f.write('\t'.join(header) + '\n')
    for site in tqdm(Site.query.all()):
        if not site.protein or not site.protein.is_preferred_isoform:
            continue
        data = [
            site.protein.gene.name, str(site.position), site.residue,
            ','.join(site.type),
            ','.join([k.name for k in site.kinases]),
            ','.join(map(str, site.pmid))
        ]

        f.write('\t'.join(data) + '\n')


@file_exporter(default_path='exported/site-specific_network_of_kinases_and_targets.tsv')
def site_specific_network_of_kinases_and_targets(f):
    header = [
        'kinase symbol',
        'target symbol',
        'kinase refseq',
        'target refseq',
        'target sequence position',
        'target amino acid'
    ]

    f.write('\t'.join(header) + '\n')
    for protein in tqdm(Protein.query, total=fast_count(Protein.query)):
        for site in protein.sites:
            for kinase in site.kinases:

                data = [
                    kinase.name,
                    protein.gene.name,
                    kinase.protein.refseq if kinase.protein else '',
                    protein.refseq,
                    site.position,
                    site.residue
                ]

                f.write('\t'.join(map(str, data)) + '\n')


@file_exporter(default_path='exported/mutations_affecting_ptm_sites.tsv')
def mutations_affecting_ptm_sites(f, sources):

    header = [
        'gene',
        'refseq',
        'mutation position',
        'mutation alt',
        'mutation summary',
        'site position',
        'site residue'
    ]

    f.write('\t'.join(header) + '\n')
    for source in sources:
        # mutation_details_model = Mutation.get_source_model(source)
        mutation_details_model = source

        for mut_details in tqdm(yield_objects(mutation_details_model.query), total=fast_count(mutation_details_model.query)):
            mutation = mut_details.mutation
            if mutation.is_ptm():
                for site in mutation.get_affected_ptm_sites():
                    protein = mutation.protein
                    summary = mut_details.summary()
                    data = [
                        protein.gene.name,
                        protein.refseq,
                        mutation.position,
                        mutation.alt,
                        ', '.join(summary) if type(summary) is list else summary,
                        site.position,
                        site.residue
                    ]

                    f.write('\t'.join(map(str, data)) + '\n')


@exporter
def mc3_muts_affecting_ptm_sites(path='exported/mc3_mutations_affecting_ptm_sites.tsv'):
    return mutations_affecting_ptm_sites([MC3Mutation], path=path)


@exporter
def clinvar_muts_affecting_ptm_sites(path='exported/clinvar_mutations_affecting_ptm_sites.tsv'):
    return mutations_affecting_ptm_sites([InheritedMutation], path=path)


@exporter
def population_muts_affecting_ptm_sites(path='exported/population_mutations_affecting_ptm_sites.tsv'):
    return mutations_affecting_ptm_sites([ExomeSequencingMutation, The1000GenomesMutation], path=path)
