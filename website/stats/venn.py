from itertools import combinations

from models import VennDiagram, Site, Protein, SiteType, SiteSource

from .store import CountStore, counter
from .table import mutation_sources, count_mutated_sites


def venn_diagram(model, name=None):

    def decorator(combination_counter):
        nonlocal name

        if not name:
            name = combination_counter.__name__

        def subset_generator(*args, **kwargs):
            cases = model.query.all()
            results = []
            for i in range(1, len(cases) + 1):
                for combination in combinations(cases, i):
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


class VennDiagrams(CountStore):

    storage_model = VennDiagram

    def __init__(self):

        # generate venn diagrams of mutated sites percentage
        for name, mutations_source in mutation_sources().items():

            @venn_diagram(SiteType, name=f'percent_of_sites_mutated_{name}')
            def percent_of_sites_mutated(combination, only_primary=True):
                sites_total = sites_by_type(combination, only_primary=only_primary)
                sites_mutated = count_mutated_sites(combination, mutations_source, only_primary=only_primary)
                return sites_mutated / sites_total

            # This one is very costly too
            # self.register(percent_of_sites_mutated)

    venn_sites_by_type = venn_diagram(SiteType)(sites_by_type)

    @venn_diagram(SiteSource)
    def sites_by_source(combination, only_primary=False):
        query = Site.query

        for source in combination:
            query = query.filter(Site.sources.any(source.id == SiteSource.id))

        if only_primary:
            query = query.join(Protein).filter(Protein.is_preferred_isoform)

        return query.count()
