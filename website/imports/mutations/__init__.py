import gzip
from abc import ABC
from abc import abstractmethod
from collections import OrderedDict
from collections import defaultdict

from sqlalchemy.orm.exc import NoResultFound

from database import db, yield_objects, remove_model, raw_delete_all
from database import bulk_ORM_insert
from database import fast_count
from database import get_highest_id
from database import restart_autoincrement
from helpers.bioinf import decode_mutation
from helpers.bioinf import is_sequence_broken
from helpers.parsers import chunked_list
from imports.protein_data import get_proteins
from models import Mutation


def make_metadata_ordered_dict(keys, metadata, get_from=None):
    """Create an OrderedDict with given keys, and values

    extracted from metadata list (or being None if not present
    in metadata list. If there is a need to choose values among
    subfields (delimited by ',') then get_from tells from which
    subfield the data should be used. This function will demand
    all keys existing in dictionary to be updated - if you want
    to loosen this requirement you can specify which fields are
    not compulsory, and should be assign with None value (as to
    import flags from VCF file).
    """
    dict_to_fill = OrderedDict(
        (
            (key, None)
            for key in keys
        )
    )

    for entry in metadata:
        try:
            # given entry is an assignment
            key, value = entry.split('=')
            if get_from is not None and ',' in value:
                value = float(value.split(',')[get_from])
        except ValueError:
            # given entry is a flag
            key = entry
            value = True

        if key in keys:
            dict_to_fill[key] = value

    return dict_to_fill


class BaseMutationsImporter:
    """Imports 'cores of mutations' - data used to build 'Mutation' instances
    so columns common for different metadata like: 'position', 'alt' etc."""

    def prepare(self):
        # reset base_mutations
        self.mutations = {}

        # for bulk_inserts it's needed to generate identifiers manually so
        # here the highest id currently in use in the database is retrieved.
        self.highest_base_id = self.get_highest_id()

    def get_highest_id(self):
        return get_highest_id(Mutation)

    def get_or_make_mutation(self, pos, protein_id, alt, is_ptm):

        key = (pos, protein_id, alt)
        if key in self.mutations:
            mutation_id = self.mutations[key][0]
        else:
            try:
                mutation = Mutation.query.filter_by(
                    position=pos, protein_id=protein_id, alt=alt
                ).one()
                mutation_id = mutation.id
            except NoResultFound:
                self.highest_base_id += 1
                mutation_id = self.highest_base_id
                self.mutations[key] = (mutation_id, is_ptm)
        return mutation_id

    def insert(self):
        for chunk in chunked_list(self.mutations.items()):
            db.session.bulk_insert_mappings(
                Mutation,
                [
                    {
                        'id': data[0],
                        'precomputed_is_ptm': data[1],
                        'position': mutation[0],
                        'protein_id': mutation[1],
                        'alt': mutation[2]
                    }
                    for mutation, data in chunk
                ]
            )
            db.session.flush()


class MutationImporter(ABC):

    default_path = None
    insert_keys = None
    model = None

    def __init__(self, proteins=None):
        self.mutations_details_pointers_grouped_by_unique_mutations = defaultdict(list)
        if not proteins:
            proteins = get_proteins()
        self.proteins = proteins
        self.broken_seq = defaultdict(list)

        # used to save 'cores of mutations': Mutation objects which have
        # columns like 'position', 'alt', 'protein' and no other details.
        self.base_importer = BaseMutationsImporter()

    @property
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

    def load(self, path=None, update=False, **ignored_kwargs):
        """Load, parse and insert mutations from given path.

        If update is True, old mutations will be updated and new added.
        Essential difference when using update is that 'update' prevents
        adding duplicates (i.e. checks if mutations already exists in the
        database) but is very slow, whereas when 'update=False', the whole
        process is very fast but not reliable for purpose of reimporting data
        without removing old mutations in the first place.

        Long story short: when importing mutations to clean/new database - use
        update=False. For updates use update=True and expect long runtime."""
        print('Loading %s:' % self.model_name)

        path = self.choose_path(path)
        self.base_importer.prepare()

        # as long as 'parse' uses 'get_or_make_mutation' method, it will
        # populate 'self.base_importer.mutations' with new tuples of data
        # necessary to create rows corresponding to 'Mutation' instances.
        mutation_details = self.parse(path)

        # first insert new 'Mutation' data
        self.base_importer.insert()

        # then insert or update details about mutation (so self.model entries)
        if update:
            self.update_details(mutation_details)
        else:
            self.insert_details(mutation_details)

        self.commit()

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

        print('Loaded %s.' % self.model_name)

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
            'AffectedSites'
        ]

        self.base_importer.prepare()

        skipped = 0
        total = 0

        with gzip.open(export_path, 'wt') as f:

            f.write('\t'.join(header) + '\n')

            for line in self.iterate_lines(path):

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
                    if len(line) == 10:
                        line.append(sites)
                    else:
                        line[10] = sites
                    f.write('\t'.join(line[:11]) + '\n')

        print(skipped / total)

    def update(self, path=None):
        """Insert new and update old mutations. Same as load(update=True)."""
        self.load(path, update=True)

    @abstractmethod
    def iterate_lines(self, path):
        pass

    @abstractmethod
    def parse(self, path):
        """Make use of self.preparse_mutations() and therefore populate
        self.base_mutations with new Mutation instances and also return
        a structure containing data to populate self.model (MutationDetails
        descendants) as to be accepted by self.insert_details()."""
        pass

    @abstractmethod
    def insert_details(self, data):
        """Create instances of self.model using provided data and add them to
        session (flushing is allowed, committing is highly not recommended).
        Use of db.session methods like 'bulk_insert_mappings' is recommended."""
        pass

    # @abstractmethod
    # TODO: make it abstract and add it to all importers, altogether with tests
    def update_details(self, data):
        """Similarly to insert_details, iterate over data which hold all
        information needed to create self.model instances but instead of
        performing bulk_inserts (and therefore being prone to creation
        of duplicates) check if each mutation already is in the database and
        if it exists - overwrite it with the new data."""
        raise NotImplementedError
        pass

    def insert_list(self, data):
        if not self.insert_keys:
            raise Exception(
                'To use insert_list, you have to specify insert_keys'
            )
        bulk_ORM_insert(self.model, self.insert_keys, data)

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

    def export_details_headers(self):
        return []

    def export_details(self, mutation):
        return [[]]

    def generate_export_path(self, only_preferred, prefix=''):
        from datetime import datetime
        import os

        export_time = datetime.utcnow()

        directory = os.path.join('exported', 'mutations')
        os.makedirs(directory, exist_ok=True)

        name_template = '{prefix}{model_name}{restrictions}-{date}.tsv.gz'

        name = name_template.format(
            prefix=prefix,
            model_name=self.model_name,
            restrictions=(
                '-primary_isoforms_only' if only_preferred else ''
            ),
            date=export_time
        )
        return os.path.join(directory, name)

    def export(self, path=None, only_primary_isoforms=False):
        """Export all mutations from this source in ActiveDriver compatible format.

        Source specific data export can be implemented with export_details method,
        while export_details_headers should provide names for respective headers.
        """
        from tqdm import tqdm
        tick = 0

        if not path:
            path = self.generate_export_path(only_primary_isoforms)

        header = [
            'gene', 'isoform', 'position',  'wt_residue', 'mut_residue'
        ] + self.export_details_headers()

        with gzip.open(path, 'wt') as f:
            f.write('\t'.join(header))

            for mutation in tqdm(yield_objects(self.model.query), total=fast_count(db.session.query(self.model))):
                tick += 1

                m = mutation.mutation

                if only_primary_isoforms and not m.protein.is_preferred_isoform:
                    continue

                dataset_specific = self.export_details(mutation)

                try:
                    ref = m.ref
                except IndexError:
                    print(
                        'Mutation: %s %s %s is exceeding the proteins sequence'
                        % (m.protein.refseq, m.position, m.alt)
                    )
                    ref = ''

                for instance in dataset_specific:
                    data = [
                        m.protein.gene.name, m.protein.refseq,
                        str(m.position), ref, m.alt
                    ] + instance

                    f.write('\n' + '\t'.join(data))

                    del data

                del mutation
                if tick % 10000 == 0:
                    import gc
                    gc.collect()

    def get_or_make_mutation(self, pos, protein_id, alt, is_ptm):
        mutation_id = self.base_importer.get_or_make_mutation(
            pos, protein_id, alt, is_ptm
        )
        return mutation_id

    def preparse_mutations(self, line):
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

    def get_or_make_mutations(self, line):
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

            for mutation_id in self.preparse_mutations(line):

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


class MutationImportManager:

    def __init__(self, lookup_dir='imports/mutations'):
        self.importers = self._discover_importers(lookup_dir)

    @staticmethod
    def _discover_importers(lookup_dir):
        import imp
        from os.path import basename
        from helpers.parsers import get_files

        importers = {}

        for path in get_files(lookup_dir, '*.py'):
            name = basename(path)[:-3]
            if name == '__init__':
                continue
            importers[name] = imp.load_source(name, path)

        return importers

    def select(self, restrict_to):
        if not restrict_to:
            return self.importers
        return {
            name: self.importers[name]
            for name in restrict_to
        }

    def explain_action(self, action, sources):
        print('{action} mutations from: {sources} source{suffix}'.format(
            action=action,
            sources=(
                ', '.join(sources)
                if set(sources) != set(self.importers.keys())
                else 'all'
            ),
            suffix='s' if len(sources) > 1 else ''
        ))

    def perform(self, action, proteins, sources='__all__', paths=None, **kwargs):
        if sources == '__all__':
            sources = self.names

        self.explain_action(action, sources)

        importers = self.select(sources)
        path = None

        for name, module in importers.items():
            if paths:
                path = paths[name]

            importer = module.Importer(proteins)
            method = getattr(importer, action)
            method(path=path, **kwargs)

        print('Mutations %sed' % action)

    @property
    def names(self):
        return self.importers.keys()
