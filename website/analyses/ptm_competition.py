from sqlalchemy import and_
from sqlalchemy.orm import aliased

from models import SiteType, Site, Protein


def ptm_sites_proximity(type_1: str, type_2: str, distance: int=7, only_preferred=True, negate_type_2=False) -> int:
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
        site_type = SiteType.query.filter_by(name=type_name).one()
        site_filter = SiteType.fuzzy_filter(site_type, join=True, site=site)
        if negate_type_2:
            site_filter = ~site_filter
        sites = sites.filter(site_filter)

    if only_preferred:
        # no need to repeat as we already joined on protein_id
        sites = sites.join(Site.protein).filter(Protein.is_preferred_isoform)

    return sites.count()
