from pathlib import Path
from warnings import warn

from pandas import read_table, to_numeric, DataFrame, concat, Series

import imports.protein_data as importers
from helpers.bioinf import aa_symbols
from imports.sites.site_importer import SiteImporter
from imports.sites.uniprot.importer import UniprotToRefSeqTrait, UniprotIsoformsTrait, UniprotSequenceAccessionTrait


class PhosphoSitePlusImporter(SiteImporter, UniprotToRefSeqTrait, UniprotIsoformsTrait, UniprotSequenceAccessionTrait):
    """PhosphoSitePlus(R) site importer.

    To use this importer one need to download relevant files from:
    https://www.phosphosite.org/staticDownloads.action

    Following files are needed:

        Kinase_Substrate_Dataset.gz
        Acetylation_site_dataset.gz
        Ubiquitination_site_dataset.gz
        Phosphorylation_site_dataset.gz
        Methylation_site_dataset.gz
        O-GlcNAc_site_dataset.gz
        O-GalNAc_site_dataset.gz

    and should be placed under data/sites/PSP directory.

    Maps sites by isoform, falls back to gene name.
    # TODO: handle kinases
    # TODO edge cases ('_') handling
    """

    requires = {importers.proteins_and_genes, importers.sequences}
    requires.update(SiteImporter.requires)

    source_name = 'PhosphoSitePlus'
    site_types = [
        'phosphorylation', 'glycosylation', 'acetylation',
        'ubiquitination', 'methylation'
    ]

    site_datasets = {
        'O-GalNAc': 'glycosylation',
        'O-GlcNAc': 'glycosylation',
        'Acetylation': 'acetylation',
        'Methylation': 'methylation',
        'Phosphorylation': 'phosphorylation',
        'Ubiquitination': 'ubiquitination'
    }

    def __init__(self, sprot_canonical=None, sprot_splice=None, mappings_path=None, dir_path='data/sites/PSP'):

        SiteImporter.__init__(self)
        UniprotToRefSeqTrait.__init__(self, mappings_path)
        UniprotIsoformsTrait.__init__(self, sprot_canonical, sprot_splice)

        self.dir_path = Path(dir_path)
        self.kinases = self.load_kinases()

    def extract_site_surrounding_sequence(self, site) -> str:
        return site['SITE_+/-7_AA']

    def add_nm_refseq_identifiers(self, sites: DataFrame):
        return sites.merge(
            self.mappings,
            left_on='sequence_accession',
            right_on='uniprot'
        )

    @staticmethod
    def extract_details(sites):
        supported_aminoacids = '|'.join(aa_symbols)

        extracted = sites.MOD_RSD.str.extract(
            r'(?P<residue>' + supported_aminoacids + ')'
            r'(?P<position>\d+)'
            r'(?:-(?P<modifiers>.*))?',
            expand=True
        )
        extracted.position = to_numeric(extracted.position)

        return extracted

    def load_dataset(self, dataset, only_literature=True):

        mod_type = self.site_datasets[dataset]
        path = self.dir_path / f'{dataset}_site_dataset.gz'

        sites = read_table(path, converters={'SITE_+/-7_AA': str.upper}, skiprows=3)

        sites.rename(columns={
            'ACC_ID': 'protein_accession',
            'GENE': 'gene'
        }, inplace=True)

        # there are four binary (1 or nan) columns describing the source of a site:
        # LT_LIT	MS_LIT	MS_CST	CST_CAT# ("CST_CAT." in R)
        # CST = "internal datasets" created by Cell Signaling Technology research group
        # LIT = based on literature reference
        # LT = from low-throughput experiments
        # MS = from mass spectroscopy
        # CST_CAT# - probably an identifier of a product sold by CST
        # (based on "Links to antibody and siRNA products
        # from cell signaling technology" https://doi.org/10.1093/nar/gkr1122)
        if only_literature:
            sites = sites.query('MS_LIT == 1 or LT_LIT == 1')

        sites = sites.query('ORGANISM == "human"')

        extracted_data = self.extract_details(sites)

        sites = concat([sites, extracted_data], axis=1)

        sites['mod_type'] = Series(mod_type for _ in sites)

        return sites

    def load_sites(self, site_datasets=tuple(site_datasets)):

        sites_by_dataset = []

        for dataset in site_datasets:

            sites = self.load_dataset(dataset)
            sites_by_dataset.append(sites)

        sites = concat(sites_by_dataset)

        sites = self.add_sequence_accession(sites)
        sites = self.add_nm_refseq_identifiers(sites)

        mapped_sites = self.map_sites_to_isoforms(sites)

        return self.create_site_objects(mapped_sites, ['refseq', 'position', 'residue', 'mod_type'])

    def repr_site(self, site):
        return f'{site.protein_accession}: ' + super().repr_site(site)

    def load_kinases(self, kinases_path='Kinase_Substrate_Dataset.gz'):

        path = self.dir_path / kinases_path

        kinases = read_table(path, converters={'SITE_+/-7_AA': str.upper}, skiprows=3)
        kinases = kinases.query('KIN_ORGANISM == "human" and SUB_ORGANISM == "human"')

        return kinases
