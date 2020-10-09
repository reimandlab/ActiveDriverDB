import gzip
from abc import abstractmethod
from types import SimpleNamespace
from warnings import warn

from pandas import read_table, to_numeric, DataFrame, read_csv, concat

from helpers.parsers import parse_fasta_file
import imports.protein_data as importers
from imports.sites.site_importer import SiteImporter


class UniprotToRefSeqTrait:

    default_mappings_path = 'data/HUMAN_9606_idmapping.dat.gz'

    def __init__(self, mappings_path=None):
        if not mappings_path:
            mappings_path = self.default_mappings_path

        self.mappings = self.load_mappings(mappings_path)

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
        return sites.merge(
            self.mappings,
            left_on='sequence_accession',
            right_on='uniprot'
        )


class UniprotIsoformsTrait:

    default_path_canonical = 'data/uniprot_sprot.fasta.gz'
    default_path_splice = 'data/uniprot_sprot_varsplic.fasta.gz'

    def __init__(
        self, sprot_canonical_path=None,
        sprot_splice_variants_path=None,
    ):
        self.sequences = self.load_sequences(
            sprot_canonical_path or self.default_path_canonical,
            sprot_splice_variants_path or self.default_path_splice
        )

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

    def is_isoform_canonical(self, isoform: str) -> bool:

        if isoform in self.sequences.splice:
            return False
        if isoform in self.sequences.canonical or isoform.endswith('-1'):
            return True

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
            if hasattr(site, 'primary_accession'):
                primary_accession = site.primary_accession
            elif site.sequence_accession.endswith('-1'):
                primary_accession = site.sequence_accession[:-2]
            else:
                return
            try:
                return self.sequences.canonical[primary_accession]
            except KeyError:
                warn(f'No sequence for {site.sequence_accession} found!')


class UniprotSequenceAccessionTrait:

    def add_sequence_accession(self, sites):

        self.mappings['is_canonical'] = self.mappings.uniprot.apply(self.is_isoform_canonical)

        canonical_mapping = self.mappings.query('is_canonical == True')
        canonical_mapping['protein_accession'], _ = canonical_mapping['uniprot'].str.split('-', 1).str

        canonical_mapping.rename(columns={'uniprot': 'sequence_accession'}, inplace=True)
        canonical_mapping.drop(columns=['refseq'], inplace=True)

        canonical_mapping = canonical_mapping.drop_duplicates()

        return sites.merge(canonical_mapping, on='protein_accession')


class UniprotImporter(UniprotToRefSeqTrait, UniprotIsoformsTrait, SiteImporter):
    """UniProt/SwissProt sites importer.

    The data can be exported and downloaded using sparql: http://sparql.uniprot.org,
    but for convenience check the pre-baked URLS in `download.sh`
    Relevant terms definition are available at: http://www.uniprot.org/docs/ptmlist

    The sparql code is available in `uniprot.sparql` file.

    Only reviewed entries (SwissProt) are considered.

    Many thanks to the author of https://www.biostars.org/p/261823/
    for describing how to use sparql to export PTM data from UniProt.

    Maps sites by isoform; fallback to gene names
    can be implemented by altering sparql query.
    """

    requires = {importers.proteins_and_genes, importers.sequences}
    requires.update(SiteImporter.requires)

    source_name = 'UniProt'

    @property
    @abstractmethod
    def default_path(self) -> str:
        """Default path to the csv file with site data"""

    def __init__(self, sprot_canonical_path=None, sprot_splice_variants_path=None, mappings_path=None):
        SiteImporter.__init__(self)
        UniprotToRefSeqTrait.__init__(self, mappings_path)
        UniprotIsoformsTrait.__init__(self, sprot_canonical_path, sprot_splice_variants_path)

    @abstractmethod
    def extract_site_mod_type(self, sites: DataFrame) -> DataFrame:
        """Extract site type information into additional columns.

        Following columns have to be returned: mod_type, residue.
        """

    def filter_sites(self, sites: DataFrame) -> DataFrame:

        # remove variant-specific modifications
        sites = sites[~sites['modifiers'].str.contains('in variant', na=False)]

        # and those which are not common
        sites = sites[~sites['modifiers'].str.contains('atypical', na=False)]

        # see: http://www.uniprot.org/help/evidences
        # ECO_0000269 = Experimental evidence
        sites = sites[sites['eco'] == 'ECO_0000269']

        return sites

    def load_sites(self, path=None, **filters):

        if not path:
            path = self.default_path

        sites = read_csv(path)

        sites.columns = [column.strip() for column in sites.columns]

        sites.position = to_numeric(sites.position.str.replace(r'\^.*', ''))

        extracted_data = self.extract_site_mod_type(sites)

        # TODO: UniProt source often uses PubMed id as citation identifier - but not always!
        # sites['pub_med_ids'] = sites.source.str.replace('http://purl.uniprot.org/citations/', '')

        sites.drop(columns=['data', 'source'], inplace=True)

        sites = concat([sites, extracted_data], axis=1)

        sites = self.filter_sites(sites)

        # only chosen site types
        sites = sites[sites.mod_type.isin(self.site_types)]

        # map uniprot to refseq:
        sites = self.add_nm_refseq_identifiers(sites)

        mapped_sites = self.map_sites_to_isoforms(sites)

        return self.create_site_objects(mapped_sites, ['refseq', 'position', 'residue', 'mod_type'])

    def repr_site(self, site):
        return f'{site.sequence_accession}: ' + super().repr_site(site)

    @staticmethod
    def split_kinases(kinases):
        return kinases.str.split(' (?:and|AND|or|OR) ')
