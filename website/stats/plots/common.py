from models import Site, SiteType

site_types_names = Site.types()
site_types = [SiteType(name=name) for name in site_types_names]
any_site_type = ''


class Motif:

    def __init__(self, name, pattern):
        self.name = name
        self.pattern = pattern


motifs = [
    Motif(pattern='.{7}N[^P][STCV].{5}', name='n_linked'),
    Motif(pattern='.{7}(TAPP|TSAPP|TV.P|[ST].P).{4}', name='o_linked'),
    Motif(pattern='(.{7}W..W.{4}|.{4}W..W.{7}|.{7}W[ST].C.{4})', name='c_linked')
]
