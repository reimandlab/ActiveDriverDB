from models import SiteType, AnySiteType

site_types_with_any = SiteType.available_types(include_any=True)
site_types = SiteType.available_types()
site_types_names = [site_type.name for site_type in site_types]
any_site_type = AnySiteType()


class Motif:

    def __init__(self, name, pattern):
        self.name = name
        self.pattern = pattern


motifs = [
    Motif(pattern='.{7}N[^P][STCV].{5}', name='n_linked'),
    Motif(pattern='.{7}(TAPP|TSAPP|TV.P|[ST].P).{4}', name='o_linked'),
    Motif(pattern='(.{7}W..W.{4}|.{4}W..W.{7}|.{7}W[ST].C.{4})', name='c_linked')
]
