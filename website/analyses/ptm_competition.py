from sqlalchemy import and_
from sqlalchemy.orm import aliased

from models import SiteType, Site, Protein, Mutation, source_manager


def site_type_filter_from_str(query, site=Site):
    if query == 'any':
        return

    if query.startswith('not'):
        query = query[4:]
        negate = True
    else:
        negate = False

    site_type = SiteType.query.filter_by(name=query).one()
    site_filter = SiteType.fuzzy_filter(site_type, join=True, site=site)

    if negate:
        site_filter = ~site_filter
    return site_filter


def ptm_sites_proximity(type_1: str, type_2: str, distance: int=7, only_preferred=True) -> int:
    site_1 = Site
    site_2 = aliased(Site)

    site_and_type = [(site_1, type_1), (site_2, type_2)]

    sites = site_1.query.join(
        site_2,
        and_(
            site_1.position.between(
                site_2.position - distance,
                site_2.position + distance
            ),
            site_1.protein_id == site_2.protein_id
        )
    )

    for site, type_name in site_and_type:
        site_filter = site_type_filter_from_str(type_name, site=site)
        if not site_filter:
            continue
        sites = sites.filter(site_filter)

    if only_preferred:
        # no need to repeat as we already joined on protein_id
        sites = sites.join(Site.protein).filter(Protein.is_preferred_isoform)

    return sites.count()


def ptm_muts_around_other_ptm_sites(
    source: str, mutation_ptm: str, other_type: str, only_preferred=True, mutation_filter=True
) -> int:
    distance = 7
    source = source_manager.source_by_name[source]
    other_site = aliased(Site)

    mut_ptm_filter = site_type_filter_from_str(mutation_ptm)
    query = (
        Mutation.query
        .join(source)
        .filter(mutation_filter)
        .join(Mutation.affected_sites).filter(mut_ptm_filter)
        .join(
            other_site,
            and_(
                Mutation.position.between(
                    other_site.position - distance,
                    other_site.position + distance
                ),
                Mutation.protein_id == other_site.protein_id
            )
        )
    )
    type_filter = site_type_filter_from_str(other_type, site=other_site)

    if type_filter is not None:
        query = query.filter(type_filter)

    if only_preferred:
        query = query.join(Site.protein).filter(Protein.is_preferred_isoform)

    return query.count()
