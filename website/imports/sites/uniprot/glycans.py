from pandas import DataFrame, Series

from helpers.bioinf import aa_names, aa_name_to_symbol
from imports.sites.uniprot.importer import UniprotImporter


class GlycosylationUniprotImporter(UniprotImporter):
    """Imports glycosylation sites from SwissProt."""

    source_name = 'Uniprot'
    site_types = ['glycosylation']
    default_path = 'data/sites/UniProt/glycosylation_sites.csv'

    def filter_sites(self, sites):

        # remove variant-specific glycosylations
        sites = sites[~sites['modifiers'].str.contains('in variant', na=False)]

        # ignore non-enzymatic events
        sites = sites.query('sugar_modifier != "glycation"')

        return sites

    def extract_site_mod_type(self, sites: DataFrame):

        supported_aminoacids = '|'.join(aa_names)

        extracted_data = sites.data.str.extract(
            r'(?P<link_type>S|N|C|O)-linked '
            r'\((?P<exact_mod_type>[^)]*?)\)'
            r'(?: \((?P<sugar_modifier>[^)]*?)\))?'
            r'(?: (?P<residue>' + supported_aminoacids + '))?'
            r'(?:; (?P<modifiers>.*))?',
            expand=True
        )
        # TODO: store the exact_mod_type data as 'site.details'?
        # The exact_mod_type is one of following:
        # 'GlcNAc...' 'GalNAc...' 'Xyl...' 'HexNAc...' 'Gal...' 'Fuc...' 'GlcNAc'
        # 'GalNAc' 'Man' 'Glc...' 'Hex...' 'Man6P...' 'Fuc' 'Hex' 'GlcA' 'GlcNAc6P'

        extracted_data['mod_type'] = Series('glycosylation' for _ in range(len(extracted_data)))

        extracted_data.residue = extracted_data.residue.replace(aa_name_to_symbol)

        return extracted_data

