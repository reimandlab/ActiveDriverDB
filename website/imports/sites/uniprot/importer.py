import gzip
from abc import abstractmethod
from types import SimpleNamespace
from warnings import warn

from pandas import read_table, to_numeric, DataFrame, read_csv, concat
from tqdm import tqdm

from helpers.parsers import parse_fasta_file
import imports.protein_data as importers
from imports.sites.site_importer import SiteImporter


class UniprotImporter(SiteImporter):
    """UniProt/SwissProt sites importer.

    The data can be exported and downloaded using sparql: http://sparql.uniprot.org
    Relevant terms definition are available at: http://www.uniprot.org/docs/ptmlist

    The sparql code is available in `uniprot.sparql` file.

    Only reviewed entries (SwissProt) are considered.

    Many thanks to the author of https://www.biostars.org/p/261823/
    for describing how to use sparql to export PTM data from UniProt.
    """

    requires = {importers.proteins_and_genes, importers.sequences}
    requires.update(SiteImporter.requires)

    source_name = 'Uniprot'

    @property
    @abstractmethod
    def default_path(self) -> str:
        """Default path to the csv file with site data"""

    def __init__(
        self, sprot_canonical_path='data/uniprot_sprot.fasta.gz',
        sprot_splice_variants_path='data/uniprot_sprot_varsplic.fasta.gz',
        mappings_path='data/HUMAN_9606_idmapping.dat.gz'
    ):

        super().__init__()
        self.mappings = self.load_mappings(mappings_path)
        self.sequences = self.load_sequences(sprot_canonical_path, sprot_splice_variants_path)

    @staticmethod
    def load_sequences(canonical_path, splice_variants_path):

        all_sequences = {}

        groups = {'canonical': canonical_path, 'splice': splice_variants_path}

        for isoform_group, path in groups.items():
            sequences = {}

            def append(protein_id, line):
                sequences[protein_id] += line

            def on_header(header):
                protein_id = header.split('|')[1]
                sequences[protein_id] = ''
                return protein_id

            parse_fasta_file(path, append, on_header, file_opener=gzip.open, mode='rt')

            all_sequences[isoform_group] = sequences

        return SimpleNamespace(**all_sequences)

    def get_sequence_of_protein(self, site):
        """Return sequence of a protein on which the site is described.

        Having no information describing which isoform is canonical
        the best way to determine which isoform to use is to check if
        an isoform is a splice variant; if it is not a splice variant,
        we know that it has to be a canonical isoform.
        """
        try:
            return self.sequences.splice[site.sequence_accession]
        except KeyError:
            try:
                return self.sequences.canonical[site.primary_accession]
            except KeyError:
                warn(f'No sequence for {site.sequence_accession} found!')

    @staticmethod
    def load_mappings(mappings_path):

        header = ['uniprot', 'type', 'refseq']
        mappings = read_table(mappings_path, names=header, converters={
            # based on observations, if an accession is primary and
            # there is only one splice variant, the sequence-related
            # mappings are identified just as ACCESSION; if there are many
            # splice variants, the canonical variant version is appended
            # after a hyphen # (e.g. ACCESSION-4).
            # Following converter appends '-1' to all accessions
            # that have no hyphen to make the mapping easier.
            'uniprot': lambda u: u if '-' in u else u + '-1'
        }).query('type == "RefSeq_NT"')

        mappings = mappings[mappings.refseq.str.startswith('NM_')]

        # drop refseq version
        mappings['refseq'], _ = mappings['refseq'].str.split('.', 1).str

        mappings.dropna(inplace=True)

        return mappings.drop(columns=['type'])

    def add_nm_refseq_identifiers(self, sites: DataFrame):

        sites = sites.merge(self.mappings, left_on='sequence_accession', right_on='uniprot')

        return sites

    @abstractmethod
    def extract_site_mod_type(self, sites: DataFrame) -> DataFrame:
        """Extract site type information into additional columns.

        Following columns have to be returned: mod_type, residue.
        """

    def filter_sites(self, sites: DataFrame) -> DataFrame:
        return sites

    def load_sites(self, path=None, **filters):

        if not path:
            path = self.default_path

        sites = read_csv(path)

        sites.position = to_numeric(sites.position.str.replace('\^.*', ''))

        extracted_data = self.extract_site_mod_type(sites)

        # TODO: source -> PubMed
        sites.drop(columns=['data', 'source', 'eco'], inplace=True)

        sites = concat([sites, extracted_data], axis=1)

        sites = self.filter_sites(sites)

        # TODO atypical?

        # only chosen site types
        sites = sites[sites.mod_type.isin(self.site_types)]

        # map uniprot to refseq:
        sites = self.add_nm_refseq_identifiers(sites)

        mapped_sites = self.map_sites_to_isoforms(sites)

        if mapped_sites.empty:
            return []

        columns_to_import = ['refseq', 'position', 'residue', 'mod_type']
        mapped_sites = mapped_sites[columns_to_import]

        site_objects = []

        print('Creating database objects:')

        for site_data in tqdm(mapped_sites.itertuples(index=False), total=len(mapped_sites)):

            site, new = self.add_site(*site_data)

            if new:
                site_objects.append(site)

        return site_objects

    def repr_site(self, site):
        return f'{site.sequence_accession}: ' + super().repr_site(site)

    @staticmethod
    def split_kinases(kinases):
        return kinases.str.split(' (?:and|AND|or|OR) ')
