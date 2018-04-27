from sqlalchemy import and_
from sqlalchemy.orm import aliased

from models import SiteType, Site


def ptm_sites_proximity(type_1: str, type_2: str, distance: int=7) -> int:
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
        sites = sites.filter(
            SiteType.fuzzy_filter(site_type, join=True, site=site)
        )

    return sites.count()
