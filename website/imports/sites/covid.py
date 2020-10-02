from typing import List
from warnings import warn

from pandas import read_table, read_excel

import imports.protein_data as importers
from imports.sites.site_importer import SiteImporter
from imports.sites.uniprot.importer import UniprotToRefSeqTrait, UniprotIsoformsTrait, UniprotSequenceAccessionTrait
from models import Site


class CovidPhosphoImporter(UniprotToRefSeqTrait, UniprotIsoformsTrait, UniprotSequenceAccessionTrait, SiteImporter):
    """SARS-CoV-2 infection related phosphorylation sites, based on:

    The Global Phosphorylation Landscape of SARS-CoV-2 Infection. Bouhaddou et al., 2020
    Published: 22-06-2020 | Version 1 | DOI: 10.17632/dpkbh2g9hy.1
    CC BY 4.0 - http://creativecommons.org/licenses/by/4.0

    Vero E6 is a cell line originating from the kidney of a female African green monkey (Chlorocebus sabaeus)
    (Osada et al., 2014) in (Bouhaddou et al., 2020).
    They aligned the Chlorocebus sabaeus sequences with human sequences
    to map the discovered sites to human protein orthologs.

    The phosphorylation was measured in infected and control cell lines (control had a mock injection)
    at 0-th and 24th hour of the experiment; the control is said to not changed much in the 24 hours (r=0.77)
    and therefore the authors used the 0th measure as a reference (Bouhaddou et al., 2020).

    We use Supplementary Table 1 which contains proteomic data of Vero E6 cells upon SARS-CoV-2 infection:
      - PhosphoDataFull: full list of unfiltered phosphorylation sites occurring upon SARS-CoV-2 infection,
      - AbundanceDataFull: full list of protein abundance measurements,
      - PhosphoDataFiltered: filtered list of all detected phosphorylation sites collapsed into single-site measurements.
      - PhosphoNOverexpressionFull: the full list of unfiltered phosphorylation sites upon N protein overexpression in Vero E6 cells.

    Article link: https://www.cell.com/cell/fulltext/S0092-8674(20)30811-4
    """
    requires = {importers.proteins_and_genes, importers.sequences}
    requires.update(SiteImporter.requires)

    source_name = 'Vero E6 (Bouhaddou et al., 2020)'
    site_types = ['phosphorylation (SARS-CoV-2)']
    adj_p_threshold = 0.05

    def __init__(
        self, sprot_canonical=None, sprot_splice=None, mappings_path=None,
    ):
        SiteImporter.__init__(self)
        UniprotToRefSeqTrait.__init__(self, mappings_path)
        UniprotIsoformsTrait.__init__(self, sprot_canonical, sprot_splice)

    def load_sites(self, file_path='data/sites/Supplemental Tables/TableS1.xlsx') -> List[Site]:
        if file_path.endswith('.xlsx'):
            sites = read_excel(file_path, sheet_name='PhosphoDataFiltered')
        else:
            assert file_path.endswith('.tsv')
            sites = read_table(file_path)

        is_site_significant = (
            (sites['Inf_24Hr.adj.pvalue'] < self.adj_p_threshold)
            &
            (~(sites['Ctrl_24Hr.adj.pvalue'] < self.adj_p_threshold))
        )

        # select significant sites only
        sites = sites.loc[is_site_significant]

        sites['residue'] = sites.site.str[0]
        is_canonical = sites['residue'].isin({'S', 'T', 'Y'})
        if any(~is_canonical):
            warn(
                f'Removing {sum(~is_canonical)} phosphorylation sites '
                f'mapped to non-canonical aminoacids: {set(sites[~is_canonical].residue)}'
            )
            sites = sites[is_canonical]

        sites['position'] = sites.site.str[1:].apply(int)
        assert all(sites['position'] > 0)

        sites.rename(columns={'uniprot': 'protein_accession'}, inplace=True)

        sites['mod_type'] = 'phosphorylation (SARS-CoV-2)'

        sites = self.add_sequence_accession(sites)
        sites = self.add_nm_refseq_identifiers(sites)

        mapped_sites = self.map_sites_to_isoforms(sites)

        mapped_sites['kinases'] = None
        mapped_sites['pub_med_ids'] = None

        return self.create_site_objects(mapped_sites)
