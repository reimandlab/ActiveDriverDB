from abc import abstractmethod
from functools import partial
from typing import List, Iterable, Union
from warnings import warn

from pandas import DataFrame, read_table, read_excel
from sqlalchemy.orm.exc import NoResultFound

import imports.protein_data as importers
from imports.sites.site_importer import SiteImporter
from imports.sites.uniprot.importer import UniprotToRefSeqTrait, UniprotIsoformsTrait, UniprotSequenceAccessionTrait
from models import Site, EventModulatingPTM, RegulatorySiteAssociation


CANONICAL_PHOSPHOSITE_RESIDUES = {'S', 'T', 'Y'}


def maybe_split_ints(value: Union[str, int], sep: str):
    return (
        [int(number) for number in value.split(sep)]
        if isinstance(value, str) else
        [int(value)]
    )


def read_excel_or_text(file_path: str, sheet_name: str):
    """Read table from a given excel sheet, unless a tsv file is given."""
    if file_path.endswith('.xlsx'):
        return read_excel(file_path, sheet_name=sheet_name)
    else:
        assert file_path.endswith('.tsv')
        return read_table(file_path)


class SiteModulatedUponEventImporter:

    @property
    @abstractmethod
    def event_reference(self) -> str:
        """The reference to the study providing the event PTM modulation data, e.g. `(Somebody et al, 2022)`"""

    @property
    @abstractmethod
    def event_name(self) -> str:
        """The name of the event modulating PTM site occupancy, e.g. `HIV infection`"""

    @property
    @abstractmethod
    def effect_size_type(self) -> str:
        """The effect size type, e.g. `log2FC`"""

    def get_or_create_event(self):
        try:
            event = EventModulatingPTM.query.filter_by(name=self.event_name).one()
            event.reference = self.event_reference
        except NoResultFound:
            event = EventModulatingPTM(
                name=self.event_name,
                reference=self.event_reference
            )
        return event

    def process_event_associated_sites(self, sites: DataFrame, canonical: set):
        """Process provided sites for a *single* PTM type.

        - remove non-canonnical sites,
        - add sequence accessions and identifiers,
        - map sites to isoforms in the database
        - add event data

        Note: make sure to only provide significant sites to this method
        as it does not implement any significance-based filterering.
        """
        is_canonical = sites['residue'].isin(canonical)
        if any(~is_canonical):
            warn(
                f'Removing {sum(~is_canonical)} phosphorylation sites'
                f' mapped to non-canonical aminoacids: {set(sites[~is_canonical].residue)}'
                f' keeping {sum(is_canonical)} sites'
            )
            sites = sites[is_canonical].copy()

        assert all(sites['position'] > 0)

        assert len(self.site_types) == 1

        sites['mod_type'] = self.site_types[0]

        sites = self.add_sequence_accession(sites)
        print(
            f'After mapping to UniProt sequence accessions got: {len(sites)} sites'
            f' (each protein has multiple UniProt isoforms)'
        )
        sites = self.add_nm_refseq_identifiers(sites)
        print(
            f'After mapping to RefSeq identifiers got: {len(sites)} sites'
            f' (each UniProt isoform can be mapped to one or more RefSeq isoforms)'
        )

        mapped_sites = self.map_sites_to_isoforms(sites)

        event = self.get_or_create_event()

        mapped_sites['event'] = event
        mapped_sites['pub_med_ids'] = self.pubmed_id
        mapped_sites['pub_med_ids'] = mapped_sites['pub_med_ids'].apply(lambda pubmed_id: [pubmed_id])

        return mapped_sites

    def add_site(
        self, refseq, position: int, residue, mod_type, pub_med_ids: Iterable[int],
        adj_p_val: float, effect_size: float, event: EventModulatingPTM
    ):
        site, created = super().add_site(refseq, position, residue, mod_type, pubmed_ids=pub_med_ids)

        association = RegulatorySiteAssociation(
            event=event,
            effect_size=effect_size,
            adjusted_p_value=adj_p_val,
            effect_size_type=self.effect_size_type,
            site_type=self.site_types_map[mod_type],
            site=site
        )
        site.associations.add(association)

        return site, created


class EnterovirusPhosphoImporter(
    SiteModulatedUponEventImporter,
    UniprotToRefSeqTrait, UniprotIsoformsTrait, UniprotSequenceAccessionTrait,
    SiteImporter
):
    """Enterovirus infection related phosphorylation sites, based on:

    Giansanti, P., Strating, J.R.P.M., Defourny, K.A.Y. et al.
    Dynamic remodelling of the human host cell proteome and phosphoproteome upon enterovirus infection.
    Nat Commun 11, 4332 (2020). https://doi.org/10.1038/s41467-020-18168-3
    CC BY 4.0 - http://creativecommons.org/licenses/by/4.0/

    Enterovirus CVB3 strain Nancy
    6 cell lines were tested in this paper: HeLa R19, BGM, HAP1, HuH7, A549, BGM, Vero E6

    We use Supplementary Data 4 which provides the phosphoproteome changes
    """
    requires = {importers.proteins_and_genes, importers.sequences}
    requires.update(SiteImporter.requires)

    source_name = '(Giansanti et al., 2020)'
    site_types = ['phosphorylation (enterovirus)']
    adj_p_threshold = 0.05

    event_name = 'CVB3 enterovirus infection'
    event_reference = '(Giansanti et al., 2020)'
    effect_size_type = 'log2FC'
    pubmed_id = 32859902

    def __init__(
        self, sprot_canonical=None, sprot_splice=None, mappings_path=None,
    ):
        SiteImporter.__init__(self)
        UniprotToRefSeqTrait.__init__(self, mappings_path)
        UniprotIsoformsTrait.__init__(self, sprot_canonical, sprot_splice)

    def load_sites(self, file_path='data/sites/2020_Giansanti/41467_2020_18168_MOESM7_ESM.xlsx') -> List[Site]:
        # 4.2 = Quantified phosphosites (in 3 out of 4 biological replica)
        sites = read_excel_or_text(file_path, sheet_name='Supplementary Data 4.2')

        is_site_significant = (
            (sites["Welch's T-test q-value 10h_CT"] < self.adj_p_threshold)
            &
            (~(sites["Welch's T-test q-value Mock_10h_CT"] < self.adj_p_threshold))
        )
        print(f'Keeping {sum(is_site_significant)} out of {len(is_site_significant)} available sites')

        # select significant sites only
        sites = sites.loc[is_site_significant].copy()

        # split rows where a single site was mapped to more than one protein into multiple rows
        columns_to_split = {
            'Positions within proteins': partial(maybe_split_ints, sep=';'),
            'Proteins': partial(str.split, sep=';')
        }
        for column, func in columns_to_split.items():
            sites[column] = sites[column].apply(func)

        sites = sites.explode(list(columns_to_split.keys()))
        print(
            f'After splitting sites to mapped proteins we have {len(sites)} sites'
        )

        sites.rename(columns={
            'Amino acid': 'residue',
            'Proteins': 'protein_accession',
            'Positions within proteins': 'position',
            "Welch's T-test q-value 10h_CT": 'adj_p_val',
            # note: while this is not directly named as "fold change",
            # is it obvious that it is it after looking at the Source Data
            # for Figure 1E (where interestingly authors used max(fold change))
            'Log2 10h_CT': 'effect_size'
        }, inplace=True)

        mapped_sites = self.process_event_associated_sites(
            sites,
            canonical=CANONICAL_PHOSPHOSITE_RESIDUES
        )

        return self.create_site_objects(
            mapped_sites,
            columns=[
                'refseq', 'position', 'residue', 'mod_type',
                'pub_med_ids', 'adj_p_val', 'effect_size', 'event'
            ]
        )


class HIVPhosphoImporter(
    SiteModulatedUponEventImporter,
    UniprotToRefSeqTrait, UniprotIsoformsTrait, UniprotSequenceAccessionTrait,
    SiteImporter
):
    """HIV infection related phosphorylation sites, based on:

    Greenwood, E.J., Matheson, N.J., Wals, K., van den Boomen, D.J., Antrobus, R., Williamson, J.C., and Lehner, P.J.
    Temporal proteomic analysis of HIV infection reveals remodelling of the host phosphoproteome by lentiviral Vif variants.
    eLife 5, e18296 (2016). https://doi.org/10.7554/eLife.18296.001
    CC BY 4.0 - http://creativecommons.org/licenses/by/4.0/

    Human CEM-T4 T cells

    We use `Figure 6—source data 1` which provides the phosphoproteome data.
    """
    requires = {importers.proteins_and_genes, importers.sequences}
    requires.update(SiteImporter.requires)

    source_name = '(Greenwood et al., 2016)'
    site_types = ['phosphorylation (HIV)']
    adj_p_threshold = 0.05

    event_name = 'HIV infection'
    event_reference = '(Greenwood et al., 2016)'
    effect_size_type = 'log2FC'
    pubmed_id = 27690223

    def __init__(
        self, sprot_canonical=None, sprot_splice=None, mappings_path=None,
    ):
        SiteImporter.__init__(self)
        UniprotToRefSeqTrait.__init__(self, mappings_path)
        UniprotIsoformsTrait.__init__(self, sprot_canonical, sprot_splice)

    def load_sites(self, file_path='data/sites/2016_Greenwood/elife-18296-fig6-data1-v3.xlsx') -> List[Site]:
        sites = read_excel_or_text(file_path, sheet_name='Figure 6 - source data 1')

        # split peptides into sites
        columns_to_split = {
            'Phosphosite Probabilities': partial(str.split, sep='; ')
        }
        for column, func in columns_to_split.items():
            sites[column] = sites[column].apply(func)

        sites = sites.explode(list(columns_to_split.keys()))
        print(f'Number of considered sites: {len(sites)}')

        site_data = (
            sites['Phosphosite Probabilities'].str.extract(
                r'^\s?(?P<residue>\w)\((?P<position_offset>\d+)\): (?P<probability>\d+\.\d+)\s?$',
            )
        )
        assert len(sites) == len(site_data)
        sites[site_data.columns] = site_data

        peptide_data = (
            sites['Position in Protein'].str.extract(
                r'(?P<peptide_protein>\w+) \[(?P<peptide_start>\d+)-(?P<peptide_end>\d+)\]'
            )
        )
        assert len(peptide_data) == len(sites)
        sites[peptide_data.columns] = peptide_data

        column_types = {
            'probability': float,
            'position_offset': int,
            'peptide_start': int,
            'peptide_end': int
        }
        for column, type_ in column_types.items():
            sites[column] = sites[column].apply(type_)

        assert all(
            sites['Peptide Sequence'].str.len()
            ==
            sites['peptide_end'] - sites['peptide_start'] + 1
        )
        assert all(sites['peptide_protein'] == sites['Protein Accession'])

        # is probability 0-100?
        assert sites['probability'].max() <= 100
        assert sites['probability'].min() >= 0
        # are we using 0-100 rather than 0-1?
        assert sites['probability'].max() > 1

        # select only sites with >75% probability
        sites = sites[sites['probability'] > 75]
        print(f'Number of sites with probability > 75%: {len(sites)}')

        is_site_significant = (
            (sites["q-value HIV WT vs Mock"] < self.adj_p_threshold)
        )
        print(f'Keeping {sum(is_site_significant)} out of {len(is_site_significant)} available sites')
        # select significant sites only
        sites = sites.loc[is_site_significant].copy()

        # calculate position
        sites['position'] = sites['peptide_start'] + sites['position_offset'] - 1

        sites.rename(columns={
            'Protein Accession': 'protein_accession',
            "q-value HIV WT vs Mock": 'adj_p_val',
            'Log2 (fold change)  HIV WT vs Mock': 'effect_size'
        }, inplace=True)

        mapped_sites = self.process_event_associated_sites(
            sites,
            canonical=CANONICAL_PHOSPHOSITE_RESIDUES
        )

        return self.create_site_objects(
            mapped_sites,
            columns=[
                'refseq', 'position', 'residue', 'mod_type',
                'pub_med_ids', 'adj_p_val', 'effect_size', 'event'
            ]
        )


class CovidPhosphoImporter(
    SiteModulatedUponEventImporter,
    UniprotToRefSeqTrait, UniprotIsoformsTrait, UniprotSequenceAccessionTrait,
    SiteImporter
):
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
      - PhosphoDataFiltered: filtered list of all detected phosphorylation sites
        collapsed into single-site measurements.
      - PhosphoNOverexpressionFull: the full list of unfiltered phosphorylation sites
        upon N protein overexpression in Vero E6 cells.

    Article link: https://www.cell.com/cell/fulltext/S0092-8674(20)30811-4
    """
    requires = {importers.proteins_and_genes, importers.sequences}
    requires.update(SiteImporter.requires)

    source_name = 'Vero E6 (Bouhaddou et al., 2020)'
    site_types = ['phosphorylation (SARS-CoV-2)']
    adj_p_threshold = 0.05

    event_name = 'SARS-CoV-2 infection'
    event_reference = '(Bouhaddou et al., 2020)'
    effect_size_type = 'log2FC'
    pubmed_id = 32645325

    def __init__(
        self, sprot_canonical=None, sprot_splice=None, mappings_path=None,
    ):
        SiteImporter.__init__(self)
        UniprotToRefSeqTrait.__init__(self, mappings_path)
        UniprotIsoformsTrait.__init__(self, sprot_canonical, sprot_splice)

    def load_sites(self, file_path='data/sites/COVID/Supplemental Tables/TableS1.xlsx') -> List[Site]:
        sites = read_excel_or_text(file_path, sheet_name='PhosphoDataFiltered')

        is_site_significant = (
            (sites['Inf_24Hr.adj.pvalue'] < self.adj_p_threshold)
            &
            (~(sites['Ctrl_24Hr.adj.pvalue'] < self.adj_p_threshold))
        )
        print(f'Keeping {sum(is_site_significant)} out of {len(is_site_significant)} available sites')

        # select significant sites only
        sites = sites.loc[is_site_significant].copy()

        sites['residue'] = sites.site.str[0]
        sites['position'] = sites.site.str[1:].apply(int)

        sites.rename(columns={
            'uniprot': 'protein_accession',
            'Inf_24Hr.adj.pvalue': 'adj_p_val',
            'Inf_24Hr.log2FC': 'effect_size'
        }, inplace=True)

        mapped_sites = self.process_event_associated_sites(
            sites,
            canonical=CANONICAL_PHOSPHOSITE_RESIDUES
        )

        return self.create_site_objects(
            mapped_sites,
            columns=[
                'refseq', 'position', 'residue', 'mod_type',
                'pub_med_ids', 'adj_p_val', 'effect_size', 'event'
            ]
        )
