from abc import ABC
from abc import abstractmethod
from collections import defaultdict
from collections import OrderedDict
from database import db
from database import get_highest_id
from database import restart_autoincrement
from helpers.bioinf import decode_mutation
from helpers.parsers import chunked_list
from helpers.parsers import read_from_gz_files
from models import Mutation
from models import Protein
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import SQLAlchemyError
from flask import current_app


def get_proteins():
    """Fetch all proteins from database as refseq => protein object mapping."""
    return {protein.refseq: protein for protein in Protein.query.all()}


def bulk_ORM_insert(model, keys, data):
    for chunk in chunked_list(data):
        db.session.bulk_insert_mappings(
            model,
            [
                dict(zip(keys, entry))
                for entry in chunk
            ]
        )
        db.session.flush()


def bulk_raw_insert(table, keys, data, bind=None):
    engine = db.get_engine(current_app, bind)   # TODO make helper in db
    for chunk in chunked_list(data):
        engine.execute(
            table.insert(),
            [
                dict(zip(keys, entry))
                for entry in chunk
            ]
        )
        db.session.flush()


def make_metadata_ordered_dict(keys, metadata, get_from=None):
    """Create an OrderedDict with given keys, and values

    extracted from metadata list (or beeing None if not present
    in metadata list. If there is a need to choose values among
    subfields (delimeted by ',') then get_from tells from which
    subfield the data should be used. This function will demand
    all keys existing in dictionary to be updated - if you want
    to loosen this requirement you can specify which fields are
    not compulsary, and should be assign with None value (as to
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
            # given entry is an assigment
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

        # for bulk_inserts it's needed to generate identificators manually so
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

    def __init__(self, proteins=None):
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

    def load(self, path=None, update=False):
        """Load, parse and insert mutations from given path.

        If update is True, old mutations will be updated and new added.
        Essential difference when using update is that 'update' prevents
        adding duplicates (i.e. checks if mutations already exists in the
        database) but is very slow, whereas when 'update=False', the whole
        process is very fast but not relaible for purpose of reimporting data
        without removing old mutations in the first place.

        Long stroy short: when importing mutations to clean/new database - use
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

            with open(report_file, 'w') as f:
                for refseq, instances in self.broken_seq.items():
                    for instance in instances:
                        f.write('\t'.join([refseq] + instance) + '\n')

            print(
                'Detected and skipped mutations with incorrectly mapped '
                'reference sequences in {0:d} isoforms. These mutations have '
                'been saved to {1} file.'.format(
                    len(self.broken_seq),
                    report_file
                )
            )

        print('Loaded %s.' % self.model_name)

    def update(self, path=None):
        """Insert new and update old mutations. Same as load(update=True)."""
        self.load(path, update=True)

    @abstractmethod
    def parse(self):
        """Make use of self.preparse_mutations() and therefore populate
        self.base_mutations with new Mutation instances and also return
        a structure containing data to populate self.model (MutationDetails
        descendants) as to be accepted by self.insert_details()."""
        pass

    @abstractmethod
    def insert_details(self, data):
        """Create instances of self.model using provided data and add them to
        session (flusing is allowed, commiting is highly not recommended).
        Use of db.sesion methods like 'bulk_insert_mappings' is recommended."""
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

    def raw_delete_all(self):
        """In sublcasses you can overwrite this function

        in order implement advanced removal behaviour"""
        count = self.model.query.delete()
        return count

    def restart_autoincrement(self):
        restart_autoincrement(self.model)
        db.session.commit()

    def remove(self, **kargs):
        """This function should stay untouched"""
        print('Removing %s:' % self.model_name)
        try:
            count = self.raw_delete_all()
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            print('Removing failed')
            raise
        self.restart_autoincrement()
        print('Removed %s entries of %s' % (count, self.model_name))

    def export(self, path=None, only_primary_isoforms=False):
        from datetime import datetime
        import os
        from tqdm import tqdm

        export_time = datetime.utcnow()

        if not path:
            directory = os.path.join('exported', 'mutations')
            os.makedirs(directory, exist_ok=True)

            name_template = '{model_name}{restrictions}-{date}.tsv'

            name = name_template.format(
                model_name=self.model_name,
                restrictions=(
                    '-primary_isoforms_only' if only_primary_isoforms else ''
                ),
                date=export_time
            )
            path = os.path.join(directory, name)

        header = [
            'gene', 'isoform', 'position',  'wt_residue', 'mut_residue'
        ]

        if self.model_name == 'CancerMutation':
            header += ['cancer_type', 'sample_id']
        elif self.model_name == 'InheritedMutation':
            header += ['disease']

        with open(path, 'w') as f:
            f.write('\t'.join(header))

            for mutation in tqdm(self.model.query.all()):

                m = mutation.mutation

                if only_primary_isoforms and not m.protein.is_preferred_isoform:
                    continue

                if self.model_name == 'CancerMutation':
                    cancer = mutation.cancer.code
                    s = mutation.samples or ''
                    samples = s.split(',')

                    dataset_specific = [
                        [cancer, sample]
                        for sample in samples
                    ]
                elif self.model_name == 'InheritedMutation':
                    dataset_specific = [
                        [d.disease_name]
                        for d in mutation.clin_data
                    ]
                else:
                    dataset_specific = [[]]

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

    def get_or_make_mutation(self, pos, protein_id, alt, is_ptm):
        mutation_id = self.base_importer.get_or_make_mutation(
            pos, protein_id, alt, is_ptm
        )
        return mutation_id

    def preparse_mutations(self, line):
        """Preparse mutations from a line of Annovar annotation file.

        Given line should be already splited by correct separator (usually
        tabubator sign). The mutations will be extracted from 10th field.
        The function gets first semicolon separated impact-list, and splits
        the list by commas. The redundancy of semicolon separated imapct-lists
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

            try:
                ref_in_db = '-'
                ref_in_db = protein.sequence[pos - 1]
                if ref != ref_in_db:
                    raise ValueError
            except (ValueError, IndexError):
                self.broken_seq[refseq].append(
                    [ref, ref_in_db, str(pos), alt]
                )
                continue

            affected_sites = protein.get_sites_from_range(pos - 7, pos + 7)
            is_ptm = bool(affected_sites)

            mutation_id = self.get_or_make_mutation(
                pos, protein.id, alt, is_ptm
            )

            yield mutation_id


class MutationImportManager:

    def __init__(self, lookup_dir='mutation_import'):
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


muts_import_manager = MutationImportManager()


def determine_strand(ref, cdna_ref, alt, cdna_alt):
    from helpers.bioinf import complement

    if (cdna_ref.lower() == ref and cdna_alt.lower() == alt):
        return '+'
    elif (
            complement(cdna_ref).lower() == ref and
            complement(cdna_alt).lower() == alt
    ):
        return '-'
    else:
        raise Exception(
            'Unable to determine strand for: ' +
            str([ref, cdna_ref, alt, cdna_alt])
        )


def import_mappings(proteins):
    print('Importing mappings:')

    from helpers.bioinf import get_human_chromosomes
    from database import bdb
    from database import bdb_refseq
    from database import make_snv_key
    from database import encode_csv

    chromosomes = get_human_chromosomes()
    broken_seq = defaultdict(list)

    bdb.reset()
    bdb_refseq.reset()

    for line in read_from_gz_files(
        'data/200616/all_variants/playground',
        'annot_*.txt.gz'
    ):
        chrom, pos, ref, alt, prot = line.rstrip().split('\t')

        assert chrom.startswith('chr')
        chrom = chrom[3:]

        assert chrom in chromosomes
        ref = ref.rstrip()

        snv = make_snv_key(chrom, pos, ref, alt)

        # new Coding Sequence Variants to be added to those already
        # mapped from given `snv` (Single Nucleotide Variation)
        new_variants = set()

        for dest in filter(bool, prot.split(',')):
            name, refseq, exon, cdna_mut, prot_mut = dest.split(':')
            assert refseq.startswith('NM_')
            # refseq = int(refseq[3:])
            # name and refseq are redundant with respect one to another

            assert exon.startswith('exon')
            exon = exon[4:]

            assert cdna_mut.startswith('c')
            cdna_ref, cdna_pos, cdna_alt = decode_mutation(cdna_mut)

            strand = determine_strand(ref, cdna_ref, alt, cdna_alt)

            assert prot_mut.startswith('p')
            # we can check here if a given reference nuc is consistent
            # with the reference amino acid. For example cytosine in
            # reference implies that there should't be a methionine,
            # glutamic acid, lysine nor arginine. The same applies to
            # alternative nuc/aa and their combinations (having
            # references (nuc, aa): (G, K) and alt nuc C defines that
            # the alt aa has to be Asparagine (N) - no other is valid).
            # Note: it could be used to compress the data in memory too
            aa_ref, aa_pos, aa_alt = decode_mutation(prot_mut)

            try:
                # try to get it from cache (`proteins` dictionary)
                protein = proteins[refseq]
            except KeyError:
                continue

            assert aa_pos == (int(cdna_pos) - 1) // 3 + 1

            try:
                assert aa_ref == protein.sequence[aa_pos - 1]
            except (AssertionError, IndexError):
                broken_seq[refseq].append((protein.id, aa_alt))
                continue

            sites = protein.get_sites_from_range(aa_pos - 7, aa_pos + 7)

            # add new item, emulating set update
            item = encode_csv(
                strand,
                aa_ref,
                aa_alt,
                cdna_pos,
                exon,
                protein.id,
                bool(sites)
            )

            new_variants.add(item)
            key = protein.gene.name + ' ' + aa_ref + str(aa_pos) + aa_alt
            bdb_refseq[key].update({refseq})

        bdb[snv].update(new_variants)

    return broken_seq
