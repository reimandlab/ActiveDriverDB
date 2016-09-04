from abc import ABC
from abc import abstractmethod
from collections import defaultdict
from collections import OrderedDict
from database import db
from helpers.bioinf import decode_mutation
from helpers.parsers import chunked_list
from helpers.parsers import read_from_gz_files
from models import Mutation
from models import Protein
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import SQLAlchemyError
from app import app


def get_proteins():
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
    engine = db.get_engine(app, bind)
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

    def get_highest_id(self):
        return Mutation.query.count() + 1

    def flush(self, mutations):
        for chunk in chunked_list(mutations.items()):
            db.session.bulk_insert_mappings(
                Mutation,
                [
                    {
                        'id': data[0],
                        'is_ptm': data[1],
                        'position': mutation[0],
                        'protein_id': mutation[1],
                        'alt': mutation[2]
                    }
                    for mutation, data in chunk
                ]
            )
            db.session.flush()


base_importer = BaseMutationsImporter()


class MutationImporter(ABC):

    default_path = None
    insert_keys = None

    def __init__(self, proteins=None):
        if not proteins:
            proteins = get_proteins()
        self.proteins = proteins
        self.broken_seq = defaultdict(list)

    @property
    def model_name(self):
        return self.model.__name__

    def load(self, path=None):
        self.base_mutations = {}
        print('Loading %s:' % self.model_name)
        if not path:
            if not self.default_path:
                raise Exception(
                    'path is required when no default_path is set'
                )
            path = self.default_path

        self.highest_base_id = base_importer.get_highest_id()
        mutation_details = self.parse(path)

        base_importer.flush(self.base_mutations)
        self.insert_details(mutation_details)

        db.session.commit()
        if self.broken_seq:
            print(
                'Detected and skipped mutations with incorrectly mapped '
                'reference sequences in {:d} isoforms.'.format(
                    len(self.broken_seq)
                )
            )
        print('Loaded %s.' % self.model_name)

    @abstractmethod
    def parse(self):
        pass

    @abstractmethod
    def insert_details(self):
        pass

    def insert_list(self, data):
        if not self.insert_keys:
            raise Exception(
                'To use insert_list, you have to specify insert_keys'
            )
        bulk_ORM_insert(self.model, self.insert_keys, data)

    def delete_all(self):

        print('Removing %s:' % self.model_name)
        try:
            count = self.model.query.delete()
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            print('Removing failed')
            raise
        print('Removed %s entries of %s:' % (count, self.model_name))

    def get_or_make_mutation(self, pos, protein_id, alt, is_ptm):

        key = (pos, protein_id, alt)
        if key in self.base_mutations:
            mutation_id = self.base_mutations[key][0]
        else:
            try:
                mutation = Mutation.query.filter_by(
                    position=pos, protein_id=protein_id, alt=alt
                ).one()
                mutation_id = mutation.id
            except NoResultFound:
                mutation_id = self.highest_base_id
                self.base_mutations[key] = (mutation_id, is_ptm)
                self.highest_base_id += 1
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
                assert ref == protein.sequence[pos - 1]
            except (AssertionError, IndexError):
                self.broken_seq[refseq].append((protein.id, alt))
                continue

            affected_sites = protein.get_sites_from_range(pos - 7, pos + 7)
            is_ptm = bool(affected_sites)

            mutation_id = self.get_or_make_mutation(
                pos, protein.id, alt, is_ptm
            )

            yield mutation_id


def get_all_importers():
    import imp
    import os
    from helpers.parsers import get_files
    importers = {}

    for raw_path in get_files('mutation_import', '*.py'):
        module_name = os.path.basename(raw_path[:-3])
        module = imp.load_source(module_name, raw_path)
        importers[module_name] = module

    return importers


def select_importers(restrict_to='__all__'):
    importers = get_all_importers()
    if restrict_to == '__all__':
        return importers
    return {
        name: importer
        for name, importer in importers.items()
        if name in restrict_to
    }


def explain_current_action(action, sources):
    print('{action} mutations from: {sources} source{suffix}'.format(
        action=action,
        sources=', '.join(sources),
        suffix='s' if len(sources) > 1 else ''
    ))


def load_mutations(proteins, sources='__all__'):
    explain_current_action('Loading', sources)

    importers = select_importers(restrict_to=sources)

    for name, module in importers.items():
        module.Importer().load()

    print('Mutations loaded')


def remove_mutations(sources='__all__'):
    explain_current_action('Removing', sources)

    importers = select_importers(restrict_to=sources)

    for name, module in importers.items():
        module.Importer().delete_all()

    print('Mutations removed')


def import_mappings(proteins):
    print('Importing mappings:')

    from helpers.bioinf import complement
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
            assert cdna_mut.startswith('c.')

            if (cdna_mut[2].lower() == ref and
                    cdna_mut[-1].lower() == alt):
                strand = '+'
            elif (complement(cdna_mut[2]).lower() == ref and
                    complement(cdna_mut[-1]).lower() == alt):
                strand = '-'
            else:
                raise Exception(line)

            cdna_pos = cdna_mut[3:-1]
            assert prot_mut.startswith('p.')
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
