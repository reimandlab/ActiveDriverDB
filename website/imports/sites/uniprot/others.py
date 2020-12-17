from pandas import DataFrame

from helpers.bioinf import aa_names, aa_name_to_symbol
from imports.sites.uniprot.importer import UniprotImporter


class OthersUniprotImporter(UniprotImporter):
    """Imports phosphorylation, methylation and acetylation sites.

    In future can be extended to import also sites of:
        amidation, formation of pyrrolidone carboxylic acid, isomerization,
        hydroxylation, sulfation, flavin-binding, cysteine oxidation and nitrosylation
    """

    # TODO: maybe just parse the 'ptmlist' instead?
    # This map bases on: http://www.uniprot.org/docs/ptmlist
    # and is a subset of terms present in Human sites
    # Note: there are many special cases not covered in there
    modifiers_map = {
        'Phospho': 'phosphorylation',
        'Pros-phospho': 'phosphorylation',
        'Tele-phospho': 'phosphorylation',
        'N-acetyl': 'acetylation',
        'N2-acetyl': 'acetylation',
        'N6-acetyl': 'acetylation',
        'O-acetyl': 'acetylation',
        'Methyl': 'methylation',
        'N-methyl': 'methylation',
        'N6-methyl': 'methylation',
        'Omega-N-methyl': 'methylation',
        'Omega-N-methylated ': 'methylation',
        'S-methyl': 'methylation',
        'Tele-methyl': 'methylation',
        'Dimethylated ': 'methylation',
        'Symmetric dimethyl': 'methylation',
        'Asymmetric dimethyl': 'methylation',
        'N6-succinyl': 'succinylation'
    }

    source_name = 'UniProt'
    site_types = set(modifiers_map.values())
    default_path = 'data/sites/UniProt/other_sites.csv'

    def extract_site_mod_type(self, sites: DataFrame):

        supported_aminoacids = '|'.join(aa_names)

        # NOTE: following approach fails for '3-oxoalanine' (which is
        # created from cysteine not alanine) and similar modification
        extracted = sites.data.str.extract(
            r'(?P<exact_mod_type>.*?)'
            r'(?P<residue>' + supported_aminoacids + ')'
            r'(?:; (?!by )(?P<modifiers>[^;]*))?'
            r'(?:; by (?P<kinases>[^;]*))?',
            expand=True
        )
        # TODO: store the exact_mod_type data as 'site.details'?

        extracted['mod_type'] = extracted.exact_mod_type.map(self.modifiers_map)

        extracted.kinases = self.split_kinases(extracted.kinases)
        extracted.residue = extracted.residue.replace(aa_name_to_symbol)

        return extracted
