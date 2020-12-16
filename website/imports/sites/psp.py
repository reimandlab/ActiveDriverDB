from pathlib import Path

from pandas import read_table, to_numeric, DataFrame, concat, Series

import imports.protein_data as importers
from helpers.bioinf import aa_symbols
from imports.sites.site_importer import SiteImporter
from imports.sites.uniprot.importer import UniprotToRefSeqTrait, UniprotIsoformsTrait, UniprotSequenceAccessionTrait


class PhosphoSitePlusImporter(UniprotToRefSeqTrait, UniprotIsoformsTrait, UniprotSequenceAccessionTrait, SiteImporter):
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
    """

    requires = {importers.proteins_and_genes, importers.sequences}
    requires.update(SiteImporter.requires)

    source_name = 'PhosphoSitePlus'
    site_types = [
        'phosphorylation', 'O-glycosylation', 'glycosylation',
        'acetylation', 'ubiquitination', 'methylation', 'sumoylation'
    ]

    site_datasets = {
        'O-GalNAc': 'O-glycosylation',
        'O-GlcNAc': 'O-glycosylation',
        'Acetylation': 'acetylation',
        'Methylation': 'methylation',
        'Phosphorylation': 'phosphorylation',
        'Ubiquitination': 'ubiquitination',
        'Sumoylation': 'sumoylation'
    }

    def __init__(self, sprot_canonical=None, sprot_splice=None, mappings_path=None, dir_path='data/sites/PSP'):

        SiteImporter.__init__(self)
        UniprotToRefSeqTrait.__init__(self, mappings_path)
        UniprotIsoformsTrait.__init__(self, sprot_canonical, sprot_splice)

        self.dir_path = Path(dir_path)
        self.kinases = self.load_kinases()

    def extract_site_surrounding_sequence(self, site) -> str:
        sequence = site['SITE_+/-7_AA']

        if sequence.startswith('_'):
            sequence = '^' + sequence.lstrip('_')

        if sequence.endswith('_'):
            return sequence.rstrip('_') + '$'
        else:
            return sequence

    def determine_left_offset(self, site) -> int:
        padded_site = site['SITE_+/-7_AA']

        if padded_site.startswith('_'):
            length = 1

            while padded_site[length] == '_':
                length += 1

            return self.sequence_offset - length
        return self.sequence_offset

    def add_kinases(self, sites):
        sites = sites.merge(
            self.kinases,
            left_on=['protein_accession', 'SITE_+/-7_AA'],
            right_on=['SUB_ACC_ID', 'SITE_+/-7_AA'],
            how='left'
        )
        # ideally would be to replace nan with None,
        # but the signature of sites does not allow
        # for that (passing value=None is understood
        # as not passing any value); 0 is not so bad
        # as it evaluates to False too.
        sites['kinases'] = sites['kinases'].fillna(value=0)
        return sites

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

        sites = read_table(path, converters={
            'SITE_+/-7_AA': str.upper
        }, skiprows=3)

        sites.rename(columns={
            'ACC_ID': 'protein_accession',
            'GENE': 'gene'
        }, inplace=True)

        # there are four numeric (a number or nan) columns describing the source of a site:
        # LT_LIT	MS_LIT	MS_CST	CST_CAT# ("CST_CAT." in R)
        # CST = "internal datasets" created by Cell Signaling Technology research group
        # LIT = based on literature reference
        # LT = from low-throughput experiments
        # MS = from mass spectroscopy
        # CST_CAT# - probably an identifier of a product sold by CST
        # (based on "Links to antibody and siRNA products
        # from cell signaling technology" https://doi.org/10.1093/nar/gkr1122)
        if only_literature:
            sites = sites.dropna(subset=['MS_LIT', 'LT_LIT'], how='all')

        sites = sites.query('ORGANISM == "human"')

        extracted_data = self.extract_details(sites)

        sites = concat([sites, extracted_data], axis=1)

        sites['mod_type'] = mod_type

        sites['psp_ids'] = Series(
            {site.MS_LIT, site.LT_LIT}
            for site in sites.itertuples(index=False)
        ).values
        # TODO: it should be possible to retrieve PUB MED ids from MS_LIT and LT_LIT
        # TODO: (or alternatively link to relevant place on PSP website)
        sites['pub_med_ids'] = None

        return sites

    def load_sites(self, site_datasets=tuple(site_datasets)):

        sites_by_dataset = []

        for i, dataset in enumerate(site_datasets, 1):
            print(f'Loading {dataset} dataset ({i} of {len(site_datasets)})')

            sites = self.load_dataset(dataset)
            sites_by_dataset.append(sites)

        sites = concat(sites_by_dataset)

        sites = self.add_sequence_accession(sites)
        sites = self.add_nm_refseq_identifiers(sites)
        sites = self.add_kinases(sites)

        mapped_sites = self.map_sites_to_isoforms(sites)

        return self.create_site_objects(mapped_sites)

    def repr_site(self, site):
        return f'{site.protein_accession}: ' + super().repr_site(site)

    def load_kinases(self, kinases_path='Kinase_Substrate_Dataset.gz'):

        path = self.dir_path / kinases_path

        kinases = read_table(path, converters={'SITE_+/-7_AA': str.upper}, skiprows=3)
        kinases = kinases.query('KIN_ORGANISM == "human" and SUB_ORGANISM == "human"')
        kinases = kinases[['SUB_ACC_ID', 'SITE_+/-7_AA', 'GENE']]

        kinases = kinases.groupby(['SUB_ACC_ID', 'SITE_+/-7_AA'], sort=False, squeeze=True)

        kinases = kinases['GENE'].apply(list).reset_index(name='kinases')

        if kinases.empty:
            return DataFrame(columns=['SUB_ACC_ID', 'SITE_+/-7_AA', 'kinases'])

        return kinases
