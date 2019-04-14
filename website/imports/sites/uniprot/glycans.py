from pandas import DataFrame, Series

from helpers.bioinf import aa_names, aa_name_to_symbol
from imports.sites.uniprot.importer import UniprotImporter


link_types = ['S', 'N', 'C', 'O']


class GlycosylationUniprotImporter(UniprotImporter):
    """Imports glycosylation sites from SwissProt."""

    source_name = 'Uniprot'
    site_types = [
        'glycosylation',
        *[f'{link_type}-glycosylation' for link_type in link_types]
    ]
    default_path = 'data/sites/UniProt/glycosylation_sites.csv'

    def filter_sites(self, sites):
        sites = super().filter_sites(sites)

        # ignore non-enzymatic events
        sites = sites.query('sugar_modifier != "glycation"')

        return sites

    def extract_site_mod_type(self, sites: DataFrame):

        supported_aminoacids = '|'.join(aa_names)
        supported_links = '|'.join(link_types)

        extracted = sites.data.str.extract(
            r'(?P<link_type>' + supported_links + ')-linked '
            r'\((?P<exact_mod_type>[^)]*?)\)'
            r'(?: \((?P<sugar_modifier>[^)]*?)\))?'
            r'(?: (?P<residue>' + supported_aminoacids + '))?'
            r'(?:; (?!by )(?P<modifiers>[^;]*))?'
            r'(?:; by (?P<kinases>[^;]*))?',
            expand=True
        )
        # TODO: store the exact_mod_type data as 'site.details'?
        # The exact_mod_type is one of following:
        # 'GlcNAc...' 'GalNAc...' 'Xyl...' 'HexNAc...' 'Gal...' 'Fuc...' 'GlcNAc'
        # 'GalNAc' 'Man' 'Glc...' 'Hex...' 'Man6P...' 'Fuc' 'Hex' 'GlcA' 'GlcNAc6P'

        # all entries that are not glycations are glycosylations
        extracted['mod_type'] = Series(
            (
                'glycation'
                if site_details.sugar_modifier == 'glycation' else
                site_details.link_type + '-glycosylation'
            )
            for site_details in extracted.itertuples()
        ).values

        extracted.kinases = self.split_kinases(extracted.kinases)
        extracted.residue = extracted.residue.replace(aa_name_to_symbol)

        return extracted

