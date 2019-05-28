import gc
import gzip
from abc import abstractmethod
from collections import defaultdict
from typing import List, Iterable

from sqlalchemy.orm import load_only
from sqlalchemy.util import classproperty
from werkzeug.utils import cached_property

from database import db, create_key_model_dict
from database.bulk import bulk_orm_insert, restart_autoincrement
from database.manage import raw_delete_all, remove_model
from helpers.bioinf import decode_mutation, is_sequence_broken
from helpers.patterns import abstract_property
from models import Protein, Mutation

from ...importer import BioImporter
from .base_importer import BaseMutationsImporter
from .exporter import MutationExporter


# rename to MutationSourceManager?
class MutationImporter(BioImporter, MutationExporter):

    @abstract_property
    def name(self):
        """Name of the mutations importer"""

    default_path = None
    insert_keys = None
    model = None

    def __init__(self, proteins=None):
        self.mutations_details_pointers_grouped_by_unique_mutations = defaultdict(list)
        self._proteins = proteins
        self.broken_seq = defaultdict(list)

        # used to save 'cores of mutations': Mutation objects which have
        # columns like 'position', 'alt', 'protein' and no other details.
        self.base_importer = BaseMutationsImporter()

    @cached_property
    def proteins(self):
        """Allows for lazy fetching of proteins.refseq -> protein

        as not all uses of importer require proteins in place.
        """
        if self._proteins:
            return self._proteins

        return create_key_model_dict(
            Protein, 'refseq',
            options=load_only('refseq', 'sequence', 'id')
        )

    @classproperty
    def model_name(self):
        return self.model.__name__

    @staticmethod
    def commit():
        db.session.commit()

    def choose_path(self, path):
        if not path:
            path = self.default_path
        if not path:
            raise Exception('path is required when no default_path is set')
        return path

    def load(self, path=None, update=False, **kwargs):
        """Load, parse and insert mutations from given path.

        If update is True, old mutations will be updated and new added.
        Essential difference when using update is that 'update' prevents
        adding duplicates (i.e. checks if mutations already exists in the
        database) but is very slow, whereas when 'update=False', the whole
        process is very fast but not reliable for purpose of reimporting data
        without removing old mutations in the first place.

        Long story short: when importing mutations to clean/new database - use
        update=False. For updates use update=True and expect long runtime."""
        print(f'Loading {self.model_name}:')

        path = self.choose_path(path)

        self._load(path, update, **kwargs)

        if self.broken_seq:
            report_file = 'broken_seq_' + self.model_name + '.log'

            headers = ['refseq', 'ref_in_seq', 'ref_in_mut', 'pos', 'alt']
            with open(report_file, 'w') as f:
                f.write('\t'.join(headers) + '\n')
                for refseq, instances in self.broken_seq.items():
                    for instance in instances:
                        f.write('\t'.join(map(str, instance)) + '\n')

            print(
                'Detected and skipped mutations with incorrectly mapped '
                'reference sequences in {0:d} isoforms. These mutations have '
                'been saved to {1} file.'.format(
                    len(self.broken_seq),
                    report_file
                )
            )

        print(f'Loaded {self.model_name}.')

    parse_kwargs = []

    def _load(self, path, update, **kwargs):

        self.base_importer.prepare()

        gc.collect()

        # as long as 'parse' uses 'get_or_make_mutation' method, it will
        # populate 'self.base_importer.mutations' with new tuples of data
        # necessary to create rows corresponding to 'Mutation' instances.
        parse_kwargs = {k: v for k, v in kwargs.items() if k in self.parse_kwargs}
        mutation_details = self.parse(path, **parse_kwargs)

        # first insert new 'Mutation' data
        self.base_importer.insert()

        # then insert or update details about mutation (so self.model entries)
        if update:
            self.update_details(mutation_details)
        else:
            self.insert_details(mutation_details)

        self.commit()

        db.session.expire_all()
        gc.collect()

    def test_line(self, line):
        """Whether the line should be imported/exported or not"""
        return True

    def modify_line(self, line: List[str]) -> List[str]:
        """Modify line before export"""
        return line

    def export_genomic_clean_fields(self, fields: List[str]) -> List[str]:
        return fields

    def export_genomic_coordinates_of_ptm(self, export_path=None, path=None, only_primary_isoforms=False):
        path = self.choose_path(path)

        if not export_path:
            export_path = self.generate_export_path(only_primary_isoforms, prefix='genomic_ptm_')

        header = [
            'Chr', 'Start', 'End', 'Ref', 'Alt',
            'Func.refGene',
            'Gene.refGene',
            'GeneDetail.refGene',
            'ExonicFunc.refGene',
            'AAChange.refGene',
            'AffectedSites',
            'RawSourceSpecificMetadata'
        ]

        self.base_importer.prepare()

        skipped = 0
        total = 0

        with gzip.open(export_path, 'wt') as f:

            f.write('\t'.join(header) + '\n')

            for line in filter(self.test_line, self.iterate_lines(path)):

                relevant_proteome_coordinates = []

                for pos, protein, alt, ref, is_ptm_related in self.preparse_mutations(line):

                    mutation_id = self.get_or_make_mutation(
                        pos, protein.id, alt, is_ptm_related
                    )
                    mutation = Mutation.query.get(mutation_id)

                    if only_primary_isoforms and not protein.is_preferred_isoform:
                        continue

                    total += 1

                    if not mutation:
                        skipped += 1
                        continue

                    assert is_ptm_related == mutation.is_ptm()

                    if is_ptm_related:
                        for site in mutation.get_affected_ptm_sites():
                            relevant_proteome_coordinates.append(
                                (pos, protein, alt, ref, site)
                            )

                if relevant_proteome_coordinates:

                    protein_mutations = []
                    sites_affected = []

                    for protein_mutation in line[9].split(','):
                        relevant = False
                        mutation_sites = []

                        for pos, protein, alt, ref, site in relevant_proteome_coordinates:
                            if (
                                protein_mutation.startswith(protein.gene_name + ':' + protein.refseq)
                                and
                                protein_mutation.endswith(ref + str(pos) + alt)
                            ):
                                relevant = True
                                mutation_sites.append(site)

                        if relevant:
                            protein_mutations.append(protein_mutation)
                            sites_affected.append(mutation_sites)

                    line = self.modify_line(line)
                    line[9] = ','.join(protein_mutations)
                    sites = (
                        ','.join(
                            ';'.join(
                                [
                                    site.protein.refseq + ':' + str(site.position) + site.residue
                                    for site in mutation_sites
                                ]
                            )
                            for mutation_sites in sites_affected
                        )
                    )
                    line = line[:10] + [sites] + self.export_genomic_clean_fields(line[10:])
                    f.write('\t'.join(line) + '\n')

        print(skipped / total)

    def update(self, path=None):
        """Insert new and update old mutations. Same as load(update=True)."""
        self.load(path, update=True)

    @abstractmethod
    def iterate_lines(self, path) -> Iterable[List[str]]:
        pass

    @abstractmethod
    def parse(self, path):
        """Make use of self.get_or_make_mutations() and therefore populate
        self.base_mutations with new Mutation instances and also return
        a structure containing data to populate self.model (MutationDetails
        descendants) as to be accepted by self.insert_details().

        To iterate lines of the Annovar-like file, use self.iterate_lines()
        """

    @abstractmethod
    def insert_details(self, data):
        """Create instances of self.model using provided data and add them to
        session (flushing is allowed, committing is highly not recommended).
        Use of db.session methods like 'bulk_insert_mappings' is recommended."""

    # @abstractmethod
    # TODO: make it abstract and add it to all importers, altogether with tests
    def update_details(self, data):
        """Similarly to insert_details, iterate over data which hold all
        information needed to create self.model instances but instead of
        performing bulk_inserts (and therefore being prone to creation
        of duplicates) check if each mutation already is in the database and
        if it exists - overwrite it with the new data."""
        raise NotImplementedError

    def insert_list(self, data):
        if not self.insert_keys:
            raise Exception(
                'To use insert_list, you have to specify insert_keys'
            )
        bulk_orm_insert(self.model, self.insert_keys, data)

    def raw_delete_all(self, model):
        """In subclasses you can overwrite this function

        in order implement advanced removal behaviour"""
        assert model == self.model
        return raw_delete_all(model)

    def restart_autoincrement(self, model):
        assert model == self.model
        restart_autoincrement(self.model)
        db.session.commit()

    def remove(self, **kwargs):
        """Do not overwrite this function"""
        remove_model(self.model, self.raw_delete_all, self.restart_autoincrement)

    def get_or_make_mutation(self, pos, protein_id, alt, is_ptm):
        mutation_id = self.base_importer.get_or_make_mutation(
            pos, protein_id, alt, is_ptm
        )
        return mutation_id

    def preparse_mutations(self, line: List[str]):
        """Preparse mutations from a line of Annovar annotation file.

        Given line should be already split by correct separator (usually
        tabulator character). The mutations will be extracted from 10th field.
        The function gets first semicolon separated impact-list, and splits
        the list by commas. The redundancy of semicolon separated impact-lists
        is guaranteed in the data by check_semicolon_separated_data_redundancy
        test from `test_data.py` script.

        For more explanation, check #43 issue on GitHub.
        """
        for mutation in [
            m.split(':')
            for m in line[9].split(';')[0].split(',')
        ]:
            refseq = mutation[1]

            # if the mutation affects a protein
            # which is not in our dataset, skip it
            try:
                protein = self.proteins[refseq]
            except KeyError:
                continue

            ref, pos, alt = decode_mutation(mutation[4])

            broken_sequence_tuple = is_sequence_broken(protein, pos, ref, alt)

            if broken_sequence_tuple:
                self.broken_seq[refseq].append(broken_sequence_tuple)
                continue

            is_ptm_related = protein.has_sites_in_range(pos - 7, pos + 7)

            yield pos, protein, alt, ref, is_ptm_related

    def get_or_make_mutations(self, line: List[str]):
        """Get or create mutations from line of Annovar annotation file and return their ids."""
        for pos, protein, alt, ref, is_ptm_related in self.preparse_mutations(line):

            mutation_id = self.get_or_make_mutation(
                pos, protein.id, alt, is_ptm_related
            )

            yield mutation_id

    def data_as_dict(self, data, mutation_id=None):
        if mutation_id:
            with_mutation = [mutation_id]
            with_mutation.extend(data)
            data = with_mutation
        return dict(zip(self.insert_keys, data))

    def look_after_duplicates(self, mutation_id, mutations_details, values):
        """To prevent inclusion of duplicate data use this function to check for duplicates
        before adding any data to mutations_details insertion list.

        For example, assuming that clinvar_mutations is an insertion list use:

            values = get_data_from_line(line)

            for mutation_id in self.get_or_make_mutations(line):

                duplicated = self.look_after_duplicates(mutation_id, clinvar_mutations, values)

                # skip unwanted duplicate
                if duplicated:
                    continue

                self.protect_from_duplicates(mutation_id, clinvar_mutations)

                clinvar_mutations.append((mutation_id, *values))
        """

        if mutation_id in self.mutations_details_pointers_grouped_by_unique_mutations:
            pointers = self.mutations_details_pointers_grouped_by_unique_mutations[mutation_id]
            for pointer in pointers:
                # first value in mutations_details store is used to keep mutation_id
                old_values = mutations_details[pointer][1:]
                if tuple(values) == tuple(old_values):
                    data = self.data_as_dict(mutations_details[pointer])
                    print(
                        'The row with: %s is a duplicate of another row '
                        '(with respect to the considered values).' % data
                    )
                    return True

    def protect_from_duplicates(self, mutation_id, mutations_details):
        """Use in tandem with look_after_duplicates method"""
        new_pointer = len(mutations_details)
        self.mutations_details_pointers_grouped_by_unique_mutations[mutation_id].append(new_pointer)


class ChunkedMutationImporter(MutationImporter):

    # if the input file is so large that it needs to be processed in chunks
    # (and the importer is able to handle chunk-by-chunk processing), what
    # should be the size of each chunk (in number of lines)
    chunk_size = None
    parse_kwargs = ['chunk_start', 'chunk_size']

    @abstractmethod
    def count_lines(self, path) -> int:
        pass

    @abstractmethod
    def parse_chunk(self, path, chunk_start, chunk_size):
        pass

    def parse(self, path, chunk_start, chunk_size):
        return self.parse_chunk(path, chunk_start, chunk_size)

    def _load(self, path, update, chunk=None):
        total = self.count_lines(path)
        chunks = (
            list(range(0, total, self.chunk_size))
            if self.chunk_size else
            [None]
        )
        if chunk is not None:
            print(f'Limitting imported chunks to {chunk+1}-th chunk out of {len(chunks)}')
            chunks = [chunks[chunk]]
        for chunk_start in chunks:
            print(f'Importing chunk from {chunk_start/total*100:.2f} to {(chunk_start + self.chunk_size)/total*100:.2f}:')
            super()._load(path, update, chunk_start=chunk_start, chunk_size=self.chunk_size)
