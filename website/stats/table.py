from collections import defaultdict

from sqlalchemy import func, distinct, case, literal_column, and_
from tqdm import tqdm

import models
from database import db
from models import Mutation, Protein, Site
from stats import Statistics


def count_mutated_sites(site_types=tuple(), model=None, only_primary=False):
    filters = [
        Mutation.protein_id == Protein.id,
        Site.protein_id == Protein.id,
        Mutation.precomputed_is_ptm
    ]
    for site_type in site_types:
        filters.append(Site.type.contains(site_type.name))
    query = (
        db.session.query(
            func.count(distinct(case(
                [
                    (
                        (
                            Mutation.position.between(
                                Site.position - 7,
                                Site.position + 7
                            )
                        ),
                        Site.id
                    )
                ],
                else_=literal_column('NULL')
            )))
        )
        .filter(and_(*filters))
        .join(Mutation, Site.protein_id == Mutation.protein_id)
    )
    if model:
        query = query.filter(Statistics.get_filter_by_sources([model]))
    else:
        query = query.filter(Mutation.is_confirmed == True)

    if only_primary:
        query = query.join(Protein).filter(Protein.is_preferred_isoform)

    return query.scalar()


def mutation_sources():
    sources = {}

    for name, source in Mutation.sources_dict.items():
        if name == 'user':
            continue
        sources[name] = Mutation.get_source_model(name)

    return sources


def source_specific_proteins_with_ptm_mutations():

    source_models = mutation_sources()
    source_models['merged'] = None

    proteins_with_ptm_muts = {}
    kinases = {}
    kinase_groups = {}
    for name, model in tqdm(source_models.items()):
        query = (
            db.session.query(distinct(Protein.id))
            .filter(Protein.has_ptm_mutations_in_dataset(model) == True)
        )
        proteins_with_ptm_muts[name] = query.count()
        kinases[name] = (
            db.session.query(distinct(models.Kinase.id))
            .join(Protein)
            .filter(Protein.has_ptm_mutations_in_dataset(model) == True)
        ).count()
        kinase_groups[name] = (
            db.session.query(distinct(models.KinaseGroup.id))
            .join(models.Kinase)
            .join(Protein)
            .filter(Protein.has_ptm_mutations_in_dataset(model) == True)
        ).count()

    return {
        'Proteins with PTM muts': proteins_with_ptm_muts,
        'Kinases with PTM muts': kinases,
        'Kinase groups with PTM muts': kinase_groups
    }


def source_specific_nucleotide_mappings():
    from database import bdb
    from genomic_mappings import decode_csv
    from models import Mutation
    from tqdm import tqdm
    from gc import collect

    mutations = defaultdict(str)

    def count_mutations(mutations_query):
        for mutation in tqdm(mutations_query, total=mutations_query.count()):
            mutations[str(mutation[0]) + mutation[1] + str(mutation[2])] += i

    sources_map = {str(i): model for i, model in enumerate(mutation_sources().values())}

    print('Loading mutations from sources:')
    for i, model in tqdm(sources_map.items(), total=len(sources_map)):
        query = (
            db.session.query(Mutation.protein_id, Mutation.alt, Mutation.position)
            .filter(Statistics.get_filter_by_sources([model]))
            # no need for '.filter(Mutation.is_confirmed==True)'
            # (if it is in source of interest, it is confirmed - we do not count MIMPs here)
            .yield_per(5000)
        )
        count_mutations(query)

    # add merged
    i = str(len(sources_map))
    sources_map[i] = 'merged'
    print('Loading merged mutations:')

    query = (
        db.session.query(Mutation.protein_id, Mutation.alt, Mutation.position)
        .filter(Mutation.is_confirmed == True)
        .yield_per(5000)
    )
    count_mutations(query)

    print('Mutations loaded')
    collect()

    def iterate_known_muts_sources():
        for value in tqdm(bdb.values(), total=len(bdb.db)):
            for item in map(decode_csv, value):
                sources = mutations.get(str(item['protein_id']) + item['alt'] + str(item['pos']))
                if sources:
                    yield sources

    counts = defaultdict(int)
    fields_ids = [source_id for source_id in sources_map.keys()]

    for sources in iterate_known_muts_sources():
        for field in fields_ids:
            if field in sources:
                counts[field] += 1

    return {
        'Nucleotide mappings': {
            sources_map[key]: value
            for key, value in counts.items()
        }
    }


def source_specific_mutated_sites():

    muts_in_ptm_sites = {}
    mimp_muts = {}
    mutated_sites = defaultdict(dict)

    site_type_queries = [models.SiteType(name='')]  # empty will match all sites
    site_type_queries.extend(models.SiteType.query)

    for name, model in mutation_sources().items():
        count = (
            Mutation.query
            .filter_by(is_confirmed=True, is_ptm_distal=True)
            .filter(Statistics.get_filter_by_sources([model]))
            .count()
        )
        muts_in_ptm_sites[name] = count

        mimp_muts[name] = (
            Mutation.query
            .filter(
                and_(
                    Statistics.get_filter_by_sources([models.MIMPMutation, model]),
                    Mutation.is_confirmed,
                )
            ).count()
        )

        for site_type in tqdm(site_type_queries):
            mutated_sites[name][site_type] = count_mutated_sites([site_type], model)

    all_mutated_sites = {}

    for site_type in tqdm(site_type_queries):
        all_mutated_sites[site_type] = count_mutated_sites([site_type])

    mutated_sites['merged'] = all_mutated_sites

    return {
        'Mutations - in PTM sites': muts_in_ptm_sites,
        'Mutations - with network-rewiring effect': mimp_muts,
        'PTM sites affected by mutations': mutated_sites
    }


def sites_counts():
    counts = {}
    site_types = ['']  # empty will match all sites
    site_types.extend(Site.types())
    for site_type in site_types:
        count = Site.query.filter(Site.type.contains(site_type)).count()
        counts[site_type] = count
    return {'PTM sites': counts}


def generate_source_specific_summary_table():
    from gc import collect

    table_chunks = [
        source_specific_proteins_with_ptm_mutations,
        source_specific_mutated_sites,
        source_specific_nucleotide_mappings,
        sites_counts
    ]
    table = {}
    for table_chunk_generator in table_chunks:
        chunk = table_chunk_generator()
        table.update(chunk)
        collect()

    print(table)

    return table
