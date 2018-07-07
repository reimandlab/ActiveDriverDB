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


@exporter
def sequences_ac(path='exported/preferred_isoforms_sequences.fa'):
    """Sequences as needed for Active Driver input.
    Includes only data from primary (preferred) isoforms."""

    create_path_if_possible(path)

    with open(path, 'w') as f:
        for gene in tqdm(Gene.query.all()):
            if not gene.preferred_isoform:
                continue
            f.write('>' + gene.name + '\n')
            f.write(gene.preferred_isoform.sequence + '\n')

    return path


@exporter
def disorder_ac(path='exported/preferred_isoforms_disorder.fa'):
    """Disorder data as needed for Active Driver input.
    Includes only data from primary (preferred) isoforms."""

    create_path_if_possible(path)

    with open(path, 'w') as f:
        for gene in tqdm(Gene.query.all()):
            if not gene.preferred_isoform:
                continue
            f.write('>' + gene.name + '\n')
            f.write(gene.preferred_isoform.disorder_map + '\n')

    return path


@exporter
def sites_ac(path='exported/sites.tsv'):
    """Sites as needed for Active Driver input.
    Includes only data from primary (preferred) isoforms."""
    header = ['gene', 'position', 'residue', 'kinase', 'pmid']

    create_path_if_possible(path)

    with open(path, 'w') as f:
        f.write('\t'.join(header) + '\n')
        for site in tqdm(Site.query.all()):
            if not site.protein or not site.protein.is_preferred_isoform:
                continue
            data = [
                site.protein.gene.name, str(site.position), site.residue,
                ','.join([k.name for k in site.kinases]),
                site.pmid
            ]

            f.write('\t'.join(data) + '\n')

    return path


@exporter
def site_specific_network_of_kinases_and_targets(path='exported/site-specific_network_of_kinases_and_targets.tsv'):
    header = [
        'kinase symbol',
        'target symbol',
        'kinase refseq',
        'target refseq',
        'target sequence position',
        'target amino acid'
    ]

    create_path_if_possible(path)

    with open(path, 'w') as f:
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

    return path


def mutations_affecting_ptm_sites(sources, path='exported/mutations_affecting_ptm_sites.tsv'):

    header = [
        'gene',
        'refseq',
        'mutation position',
        'mutation alt',
        'mutation summary',
        'site position',
        'site residue'
    ]

    create_path_if_possible(path)

    with open(path, 'w') as f:
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

    return path


@exporter
def mc3_muts_affecting_ptm_sites(path='exported/mc3_mutations_affecting_ptm_sites.tsv'):
    return mutations_affecting_ptm_sites([MC3Mutation], path)


@exporter
def clinvar_muts_affecting_ptm_sites(path='exported/clinvar_mutations_affecting_ptm_sites.tsv'):
    return mutations_affecting_ptm_sites([InheritedMutation], path)


@exporter
def population_muts_affecting_ptm_sites(path='exported/population_mutations_affecting_ptm_sites.tsv'):
    return mutations_affecting_ptm_sites([ExomeSequencingMutation, The1000GenomesMutation], path)
