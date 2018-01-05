from collections import defaultdict

from pandas import read_table, Series, to_numeric, DataFrame
from tqdm import tqdm

from helpers.parsers import parse_fasta_file
import imports.protein_data as importers
from imports.sites.site_importer import SiteImporter


class HPRDImporter(SiteImporter):

    requires = {importers.proteins_and_genes, importers.sequences}
    requires.update(SiteImporter.requires)

    site_types = ['phosphorylation', 'glycosylation', 'acetylation']

    def __init__(self, sequences_path='PROTEIN_SEQUENCES.txt', mappings_path='HPRD_ID_MAPPINGS.txt', dir_path='data/raw/HPRD/FLAT_FILES_072010/'):

        super().__init__()
        self.mappings = self.load_mappings(dir_path + mappings_path)
        self.sequences = self.load_sequences(dir_path + sequences_path)

    @staticmethod
    def load_sequences(path):
        sequences = defaultdict(str)

        def append(header, line):
            hprd_isoform_id = header.split('|')[1]
            sequences[hprd_isoform_id] += line

        parse_fasta_file(path, append)
        return sequences

    def get_sequence_of_protein(self, site):
        return self.sequences[site.substrate_isoform_id]

    @staticmethod
    def load_mappings(mappings_path):
        header = [
            'hprd_id', 'geneSymbol', 'nucleotide_accession', 'protein_accession',
            'entrezgene_id', 'omim_id', 'swissprot_id', 'main_name'
        ]
        mappings = read_table(mappings_path, names=header).dropna(subset=['nucleotide_accession'])
        return mappings

    def add_nm_refseq_identifiers(self, sites: DataFrame):

        identifiers_subset = self.mappings[['nucleotide_accession', 'protein_accession']]

        sites = sites.merge(identifiers_subset, left_on='substrate_refseq_id', right_on='protein_accession')

        sites['nucleotide_accession'], _ = sites['nucleotide_accession'].str.split('.', 1).str

        sites.rename({'nucleotide_accession': 'refseq_nm'}, axis='columns', inplace=True)

        return sites

    def load_sites(self, path='data/raw/HPRD/FLAT_FILES_072010/POST_TRANSLATIONAL_MODIFICATIONS.txt', **filters):

        header = (
            'substrate_hprd_id', 'substrate_gene_symbol', 'substrate_isoform_id', 'substrate_refseq_id', 'site',
            'residue', 'enzyme_name', 'enzyme_hprd_id', 'modification_type', 'experiment_type', 'reference_id'
        )

        all_sites = read_table(path, names=header, converters={
            'site': lambda pos: pos.rstrip(';-'),
            'modification_type': str.lower,
            'reference_id': lambda ref: str(ref).split(',')
        })

        # only chosen site types
        sites = all_sites[all_sites.modification_type.isin(self.site_types)]

        # conversion of site position to numeric can be only performed after filtering out
        # PTM like bisulfide bounds (for which positions of both ends are separated by ';')
        sites['site'] = to_numeric(sites['site'])

        # map NP refseq to NM:
        sites = self.add_nm_refseq_identifiers(sites)

        normalized_names = {
            'refseq_nm': 'refseq',
            'site': 'position',
            'modification_type': 'mod_type',
            'enzyme_name': 'kinases'
        }

        sites.rename(normalized_names, axis='columns', inplace=True)

        # additional "sequence" column is needed to map the site across isoforms
        sequences = sites.apply(self.extract_site_surrounding_sequence, axis=1)
        offsets = sites.apply(self.determine_left_offset, axis=1)
        sites = sites.assign(sequence=Series(sequences), left_sequence_offset=Series(offsets))

        # remove unwanted columns:
        sites = sites[
            [
                'refseq', 'position', 'residue', 'mod_type',
                'reference_id', 'kinases', 'sequence', 'left_sequence_offset'
            ]
        ]

        # sites loaded so far were explicitly defined in HPRD files
        explicit_sites = sites

        inferred_sites = self.map_sites_to_isoforms(explicit_sites.iterrows())

        sites = sites.append(inferred_sites)

        # forget about the sequence column (no longer need)
        del sites['sequence']
        del sites['left_sequence_offset']

        site_objects = []

        print('Creating database objects:')
        for site_data in tqdm(sites.itertuples(index=False), total=len(sites)):

            site, new = self.add_site(*site_data)

            if new:
                site_objects.append(site)

        return site_objects
