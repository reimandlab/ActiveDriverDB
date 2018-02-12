from functools import partial
from itertools import combinations

from models import VennDiagram, Site, Protein, SiteType, SiteSource, Mutation

from .store import CountStore, counter
from .table import mutation_sources, count_mutated_sites


def all_combinations(items, min_length=1):
    for i in range(min_length, len(items) + 1):
        for combination in combinations(items, i):
            yield combination


def venn_diagram(cases=None, model=None, name=None):
    assert cases or model

    def decorator(combination_counter):
        nonlocal name

        if not name:
            name = combination_counter.__name__

        def subset_generator(self, *args, **kwargs):
            nonlocal cases

            if model:
                cases = model.query.all()

            results = []

            for combination in all_combinations(cases):
                result = {
                    'sets': [c.name for c in combination],
                    'size': combination_counter(combination, *args, **kwargs)
                }
                results.append(result)
            return results

        return counter(subset_generator, name=name)
    return decorator


def sites_by_type(combination, only_primary=True):
    query = Site.query

    for site_type in combination:
        query = query.filter(Site.type.contains(site_type.name))

    if only_primary:
        query = query.join(Protein).filter(Protein.is_preferred_isoform)

    return query.count()


def mutation_by_source(combination, site_type=None, only_within_ptm_sites=False, only_primary=False):

    query = (
        Mutation.query
        .filter(Mutation.in_sources(*combination))
    )

    if only_within_ptm_sites:
        # query = query.filter(Mutation.is_ptm_distal == True)
        query = query.filter(Mutation.precomputed_is_ptm)

    if site_type:
        query = query.filter(Mutation.affected_sites.any(Site.type.contains(site_type)))

    if only_primary:
        query = query.join(Protein).filter(Protein.is_preferred_isoform)

    return query.count()


def sites_by_source(combination, site_type=None, only_primary=False):
    query = Site.query

    for source in combination:
        query = query.filter(Site.sources.any(source.id == SiteSource.id))

    if site_type:
        query = query.filter(Site.type.contains(site_type))

    if only_primary:
        query = query.join(Protein).filter(Protein.is_preferred_isoform)

    return query.count()


class VennDiagrams(CountStore):

    storage_model = VennDiagram

    def __init__(self):

        # generate venn diagrams of mutated sites percentage
        for name, mutations_source in mutation_sources().items():

            count_mutated = partial(count_mutated_sites, model=mutations_source)
            sites_mutated = venn_diagram(model=SiteType, name=f'sites_mutated_{name}')(count_mutated)

            self.register(sites_mutated)

        for site_type in SiteType.query:

            count_mutations_affecting_ptms = partial(
                mutation_by_source, site_type=site_type
            )
            ptm_mutations_by_mutation_source = venn_diagram(
                cases=mutation_sources().values(),
                name=f'{site_type.name}_mutations_by_source'
            )(count_mutations_affecting_ptms)

            self.register(ptm_mutations_by_mutation_source)

            count_sites = partial(
                sites_by_source,
                site_type=site_type
            )
            ptm_sites_by_source = venn_diagram(
                model=SiteSource,
                name=f'{site_type.name}_sites_by_source'
            )(count_sites)
            self.register(ptm_sites_by_source)

    venn_sites_by_type = venn_diagram(model=SiteType)(sites_by_type)

    @venn_diagram(model=SiteSource)
    def sites_by_source(combination, only_primary=False):
        return sites_by_source(combination, only_primary=only_primary)

    @venn_diagram(cases=mutation_sources().values())
    def mutation_by_source(combination):
        return mutation_by_source(combination)
