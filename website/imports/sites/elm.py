from pandas import read_table, DataFrame, Series

import imports.protein_data as importers
from imports.sites.site_importer import SiteImporter
from imports.sites.uniprot.importer import UniprotToRefSeqTrait, UniprotIsoformsTrait, UniprotSequenceAccessionTrait


class PhosphoELMImporter(SiteImporter, UniprotToRefSeqTrait, UniprotIsoformsTrait, UniprotSequenceAccessionTrait):
    """Phospho.ELM site importer.

    To use this importer one need to download relevant files from:
    http://phospho.elm.eu.org/dataset.html

    File named 'phosphoELM_all_latest.dump.tgz' should be unpacked:

        tar -xvzf phosphoELM_all_latest.dump.tgz

    and placed under data/sites/ELM directory.

    Maps sites by isoform, does not fall back to gene name.
    """

    requires = {importers.proteins_and_genes, importers.sequences}
    requires.update(SiteImporter.requires)

    source_name = 'Phospho.ELM'
    site_types = ['phosphorylation']

    def __init__(
        self, sprot_canonical=None, sprot_splice=None, mappings_path=None,
     ):

        SiteImporter.__init__(self)
        UniprotToRefSeqTrait.__init__(self, mappings_path)
        UniprotIsoformsTrait.__init__(self, sprot_canonical, sprot_splice)

    def get_sequence_of_protein(self, site) -> str:
        return site.protein_sequence

    def add_nm_refseq_identifiers(self, sites: DataFrame):
        return sites.merge(
            self.mappings,
            left_on='sequence_accession',
            right_on='uniprot'
        )

    def load_sites(self, dump_file_path='data/sites/ELM/phosphoELM_all_2015-04.dump'):

        sites = read_table(dump_file_path, converters={
            'kinases': lambda k: str(k).upper().split(',')
        }, na_values=['N.N.'])

        # TODO: filter out without pubmed id?
        # make pmids iterable and make sites with none evaluate to False
        sites.pmids = sites.pmids.apply(
            lambda ref: [int(ref)]
            if ref == ref      # if not nan
            else []
        )

        sites.rename(columns={
            'sequence': 'protein_sequence',
            'acc': 'protein_accession',
            'code': 'residue',
            'pmids': 'pub_med_ids'
        }, inplace=True)

        sites = sites.query('species == "Homo sapiens"')
        sites['mod_type'] = 'phosphorylation'

        sites = self.add_sequence_accession(sites)
        sites = self.add_nm_refseq_identifiers(sites)

        mapped_sites = self.map_sites_to_isoforms(sites)

        return self.create_site_objects(mapped_sites)

    def repr_site(self, site):
        return f'{site.protein_accession}: ' + super().repr_site(site)
