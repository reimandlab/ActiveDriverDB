from helpers.parsers import parse_tsv_file
from imports.sites.site_importer import SiteImporter


class PTMVarImporter(SiteImporter):
    """Imports from mapped list generated with PTMvar."""

    source_name = 'PTMvar'

    site_types = [
        'phosphorylation', 'acetylation',
        'ubiquitination', 'methylation'
    ]

    def __init__(self):
        super().__init__()

    def load_sites(self, path='data/site_table.tsv'):
        """Load sites from given file altogether with kinases which
        interact with these sites - kinases already in database will
        be reused, unknown kinases will be created

        Args:
            path: to tab-separated-values file with sites to load

        Returns:
            list of created sites
        """
        header = ['gene', 'position', 'residue', 'enzymes', 'pmid', 'type']

        sites = []

        def parser(line):

            refseq, position, residue, kinases_str, pmids, mod_types = line

            site_kinase_names = filter(bool, kinases_str.split(','))
            pmids = pmids.split(',')

            for mod_type in mod_types.split(','):
                site, is_new = self.add_site(refseq, int(position), residue, mod_type, pmids, site_kinase_names)

                if is_new:
                    sites.append(site)

        parse_tsv_file(path, parser, header)

        return sites

