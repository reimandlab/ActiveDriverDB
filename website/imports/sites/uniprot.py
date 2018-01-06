import gzip
from types import SimpleNamespace

from pandas import read_table, Series, to_numeric, DataFrame, read_csv, concat
from tqdm import tqdm

from helpers.bioinf import aa_name_to_symbol, aa_names
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
    site_types = ['glycosylation']

    def __init__(
        self, sprot_canonical_path='data/uniprot_sprot.fasta.gz',
        sprot_splice_variants_path='uniprot_sprot_varsplic.fasta.gz',
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
            return self.sequences.canonical[site.primary_accession]

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

    def load_sites(self, path='data/sites/UniProt/glycosylation_sites.sparql.csv', **filters):

        sites = read_csv(path)

        sites.position = to_numeric(sites.position.str.replace('\^.*', ''))

        supported_aminoacids = '|'.join(aa_names)

        # TODO: This pattern works for glycosylation sites only.
        extracted_data = sites.data.str.extract(
            r'(?P<link_type>S|N|C|O)-linked '
            r'\((?P<mod_type>[^)]*?)\)'
            r'(?: \((?P<sugar_modifier>[^)]*?)\))?'
            r'(?: (?P<residue>' + supported_aminoacids + '))?'
            r'(?:; (?P<modifiers>.*))?',
            expand=True
        )

        # TODO: source -> PubMed
        sites.drop(columns=['data', 'source', 'eco'], inplace=True)

        sites = concat([sites, extracted_data], axis=1)

        # remove variant-specific glycosylations
        sites = sites[~sites['modifiers'].str.contains('in variant', na=False)]

        # ignore non-enzymatic events
        sites = sites.query('sugar_modifier != "glycation"')

        # TODO: amend sparql query to avoid manual re-assignment?
        # TODO: store the exact type data as 'site.details'?
        # 'GlcNAc...' 'GalNAc...' 'Xyl...' 'HexNAc...' 'Gal...' 'Fuc...' 'GlcNAc'
        # 'GalNAc' 'Man' 'Glc...' 'Hex...' 'Man6P...' 'Fuc' 'Hex' 'GlcA' 'GlcNAc6P'
        mod_type_map = {'GlcNAc...': 'glycosylation'}
        sites.mod_type = sites.mod_type.replace(mod_type_map)

        # TODO atypical?
        sites.residue = sites.residue.replace(aa_name_to_symbol)

        # only chosen site types
        sites = sites[sites.mod_type.isin(self.site_types)]

        # map uniprot to refseq:
        sites = self.add_nm_refseq_identifiers(sites)

        # additional "sequence" column is needed to map the site across isoforms
        sequences = sites.apply(self.extract_site_surrounding_sequence, axis=1)
        offsets = sites.apply(self.determine_left_offset, axis=1)
        sites = sites.assign(sequence=Series(sequences), left_sequence_offset=Series(offsets))

        # remove unwanted columns:
        sites = sites[
            [
                'refseq', 'position', 'residue', 'mod_type',
                'sequence', 'left_sequence_offset'
            ]
        ]
        # sites loaded so far were explicitly defined in UniProt files
        mapped_sites = self.map_sites_to_isoforms(sites.itertuples(index=False))

        # from now, only sites which really appear in isoform sequences
        # in our database will be considered

        # forget about the sequence column (no longer need)
        mapped_sites.drop(columns=['sequence', 'left_sequence_offset'], inplace=True)

        site_objects = []

        print('Creating database objects:')

        for site_data in tqdm(mapped_sites.itertuples(index=False), total=len(mapped_sites)):

            site, new = self.add_site(*site_data)

            if new:
                site_objects.append(site)

        return site_objects
