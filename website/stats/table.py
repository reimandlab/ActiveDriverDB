from collections import defaultdict
from typing import Iterable, Dict, Callable

from sqlalchemy import distinct, and_
from tqdm import tqdm

import models
from database import db
from models import Mutation, Protein, Site
from models import confirmed_mutation_sources as mutation_sources, ensure_mutations_are_precomputed


PROTEINS_CACHE = {}


def count_mutations_in_sites(
    site_types: Iterable[models.SiteType] = tuple(), models=None,
    only_primary=False,
    custom_filters=None,
    custom_joins=None
):
    def counter(mutations, sites):
        count = 0
        positions_of_matched_sites = [
            site.position for site in sites
        ]
        for mutation in mutations:
            mutation_position = mutation.position
            affects_any_site = False
            for site_position in positions_of_matched_sites:
                if abs(mutation_position - site_position) < 8:
                    affects_any_site = True
                    break
            if affects_any_site:
                count += 1
        return count

    return count_ptm(
        site_types=site_types, models=models, only_primary=only_primary,
        counter=counter, custom_filters=custom_filters,
        custom_joins=custom_joins
    )


def count_mutated_sites(
    site_types: Iterable[models.SiteType] = tuple(), models=None,
    only_primary=False,
    custom_filters=None,
    custom_joins=None
):
    def counter(mutations, sites):
        count = 0
        mutation_positions = {
            mutation.position
            for mutation in mutations
        }
        for site in sites:
            site_position = site.position
            for mutation_position in mutation_positions:
                if abs(mutation_position - site_position) < 8:
                    count += 1
                    break
        return count

    return count_ptm(
        site_types=site_types, models=models, only_primary=only_primary,
        counter=counter, custom_filters=custom_filters,
        custom_joins=custom_joins
    )


def count_sites(
    site_types: Iterable[models.SiteType] = tuple(),
    only_primary=False
):
    def counter(mutations, sites):
        return len(sites)

    return count_ptm(
        counter=counter,
        site_types=site_types, only_primary=only_primary
    )


def count_mutations(**kwargs):
    def counter(mutations, sites):
        return len(list(mutations))

    return count_ptm(
        counter=counter,
        **kwargs
    )


def count_ptm(
    counter, site_types: Iterable[models.SiteType] = tuple(), models=None,
    only_primary=False, site_mode='any',
    custom_filters=None,
    custom_joins=None
):
    assert site_mode in {'any', 'all', 'none'}

    from sqlalchemy.orm import load_only, subqueryload

    site_types = set(site_types)

    if only_primary in PROTEINS_CACHE:
        print('Reusing cached proteins...')
        proteins = PROTEINS_CACHE[only_primary]
    else:
        print('Retrieving and caching proteins...')
        proteins = Protein.query.options(
            load_only('id'),
            subqueryload(Protein.sites)
        )
        print(proteins)
        if only_primary:
            proteins = proteins.filter(Protein.is_preferred_isoform)
        proteins = proteins.all()
        PROTEINS_CACHE[only_primary] = proteins

    count = 0

    is_any_site_type = len(site_types) == 1 and next(iter(site_types)).name == ''

    mutation_query_base = (
        Mutation.query
        .options(load_only('position'))
    )

    if custom_joins:
        for join in custom_joins:
            mutation_query_base = mutation_query_base.join(join)

    if custom_filters:
        for filter in custom_filters:
            mutation_query_base = mutation_query_base.filter(filter)

    any_site_mode = site_mode == 'any'
    none_site_mode = site_mode == 'none'

    for protein in tqdm(proteins):
        if none_site_mode:
            sites = None
        else:
            if is_any_site_type:
                sites = list(protein.sites)
            elif any_site_mode:
                sites = [
                    site for site in protein.sites
                    # if any in intersection
                    if site_types & site.types
                ]
            else:
                sites = [
                    site for site in protein.sites
                    # if all site_types are present in site.types
                    if not site_types - site.types
                ]
            if not sites:
                continue
        from sqlalchemy import or_
        mutations = (
            mutation_query_base
            .filter(Mutation.protein==protein)
        )
        if models:
            mutations = mutations.filter(Mutation.in_sources(*models, conjunction=or_))
        count += counter(mutations, sites)

    return count


TableChunk = Dict[str, Dict[str, int]]


def source_specific_proteins_with_ptm_mutations() -> TableChunk:

    source_models = mutation_sources()
    source_models['Any mutation'] = None

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


def source_specific_nucleotide_mappings() -> TableChunk:
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
            .filter(Mutation.in_sources(model))
            # no need for '.filter(Mutation.is_confirmed==True)'
            # (if it is in source of interest, it is confirmed - we do not count MIMPs here)
            .yield_per(5000)
        )
        count_mutations(query)

    # add merged
    i = str(len(sources_map))
    sources_map[i] = 'Any mutation'
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


def mutations_in_sites() -> TableChunk:

    # is_ptm_distal relies on precomputation
    ensure_mutations_are_precomputed('mutations_in_sites')

    muts_in_ptm_sites = {}
    mimp_muts = {}

    for name, model in mutation_sources().items():
        print(name)
        count = (
            Mutation.query
            .filter_by(is_confirmed=True, is_ptm_distal=True)
            .filter(Mutation.in_sources(model))
            .count()
        )
        muts_in_ptm_sites[name] = count

        mimp_muts[name] = (
            Mutation.query
            .filter(
                and_(
                    Mutation.in_sources(models.MIMPMutation, model),
                    Mutation.is_confirmed,
                )
            ).count()
        )
    return {
        'Mutations - in PTM sites': muts_in_ptm_sites,
        'Mutations - with network-rewiring effect': mimp_muts,
    }


def get_site_type_queries():
    site_type_queries = {
        'any type': [models.SiteType(name='')]   # empty will match all sites
    }
    site_type_queries.update({
        site_type.name: [site_type]
        for site_type in models.SiteType.query
    })

    site_types_with_subtypes = {
        f'{site_type.name} (including subtypes)': [site_type, *site_type.sub_types]
        for site_type in models.SiteType.query
        if site_type.sub_types
    }
    site_type_queries.update(site_types_with_subtypes)
    return site_type_queries


def get_mutation_groups():
    groups = {
        **{
            f'ClinVar {subset_name}': dict(
                models=[models.InheritedMutation],
                custom_filters=[models.InheritedMutation.significance_set_filter(subset_name)],
                custom_joins=[models.InheritedMutation, models.ClinicalData]
            )
            for subset_name in models.ClinicalData.significance_subsets
        },
        **{
            name: dict(models=[model])
            for name, model in mutation_sources().items()
        },
        **{
            'Cancer': dict(models=[models.MC3Mutation, models.PCAWGMutation]),
            'Population': dict(models=[models.ExomeSequencingMutation, models.The1000GenomesMutation]),
            'Any mutation': dict(models=list(mutation_sources().values()))
        }
    }
    return groups


def source_specific(counter, only_primary=False) -> TableChunk:
    site_type_queries = get_site_type_queries()

    counts = defaultdict(dict)

    mutations_groups = get_mutation_groups()

    mutations_progress = tqdm(mutations_groups.items(), total=len(mutations_groups))
    for name, kwargs in mutations_progress:
        mutations_progress.set_postfix({'mutation': name})
        site_progress = tqdm(site_type_queries.items(), total=len(site_type_queries))
        for site_query_name, site_types in site_progress:
            site_progress.set_postfix({'site': site_query_name})
            counts[name][site_query_name] = counter(site_types, only_primary=only_primary, **kwargs)

    return dict(counts)


def source_specific_mutated_sites(only_primary=False) -> TableChunk:
    return source_specific(counter=count_mutated_sites, only_primary=only_primary)


def source_specific_mutations_in_sites(only_primary=False) -> TableChunk:
    return source_specific(counter=count_mutations_in_sites, only_primary=only_primary)


def sites_counts(only_primary=False, method='client-side') -> TableChunk:
    assert method in {'client-side', 'server-side'}

    counts = {}

    if method == 'server-side':
        for site_type in models.SiteType.available_types(include_any=True):
            query = site_type.filter(Site.query)
            if only_primary:
                query = query.join(Protein).filter(Protein.is_preferred_isoform)
            count = query.count()
            counts[site_type] = count
    else:
        site_type_queries = get_site_type_queries()
        for site_query_name, site_types in tqdm(site_type_queries.items(), total=len(site_type_queries)):
            counts[site_query_name] = count_sites(site_types, only_primary=only_primary)

    return {'PTM sites': counts}


def mutations_counts(only_primary=False) -> TableChunk:
    counts = {}

    mutations_groups = get_mutation_groups()

    mutations_progress = tqdm(mutations_groups.items(), total=len(mutations_groups))
    for name, kwargs in mutations_progress:
        mutations_progress.set_postfix({'mutation': name})
        counts[name] = count_mutations(only_primary=only_primary, **kwargs, site_mode='none')

    return {'Mutations': counts}


def generate_source_specific_summary_table():
    from gc import collect

    table_chunks: Dict[str, Callable[[], TableChunk]] = {
        'Proteins': source_specific_proteins_with_ptm_mutations,
        'Mutations in sites': source_specific_mutations_in_sites,
        'PTM sites affected by mutations': source_specific_mutated_sites,
        'Nucleotide mappings': source_specific_nucleotide_mappings,
        'Sites': sites_counts,
        'Mutations': mutations_counts
    }
    table = {}
    for chunk_name, table_chunk_generator in table_chunks.items():
        print(chunk_name)
        chunk = table_chunk_generator()
        print(chunk)
        table[chunk_name] = chunk
        collect()

    print(table)

    return table
