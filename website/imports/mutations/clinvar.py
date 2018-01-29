from collections import OrderedDict

from sqlalchemy.orm.exc import NoResultFound
from models import InheritedMutation, Disease
from models import ClinicalData
from helpers.parsers import parse_tsv_file
from helpers.parsers import gzip_open_text
from database import get_or_create
from database.bulk import get_highest_id, bulk_orm_insert, restart_autoincrement
from database import db

from .mutation_importer import MutationImporter
from .mutation_importer.helpers import make_metadata_ordered_dict


class ClinVarImporter(MutationImporter):

    name = 'clinvar'
    model = InheritedMutation
    default_path = 'data/mutations/clinvar_muts_annotated.txt.gz'
    header = [
        'Chr', 'Start', 'End', 'Ref', 'Alt', 'Func.refGene', 'Gene.refGene',
        'GeneDetail.refGene', 'ExonicFunc.refGene', 'AAChange.refGene', 'V11',
        'V12', 'V13', 'V14', 'V15', 'V16', 'V17', 'V18', 'V19', 'V20', 'V21'
    ]
    insert_keys = (
        'mutation_id',
        'db_snp_ids',
        'is_low_freq_variation',
        'is_validated',
        'is_in_pubmed_central',
    )

    @staticmethod
    def _beautify_disease_name(name):
        return name.replace('\\x2c', ',').replace('_', ' ')

    def parse(self, path):
        clinvar_mutations = []
        clinvar_data = []
        duplicates = 0
        new_diseases = OrderedDict()

        clinvar_keys = (
            'RS',
            'MUT',
            'VLD',
            'PMC',
            'CLNSIG',
            'CLNDBN',
            'CLNREVSTAT',
        )

        highest_disease_id = get_highest_id(Disease)

        def clinvar_parser(line):
            nonlocal highest_disease_id, duplicates

            metadata = line[20].split(';')

            clinvar_entry = make_metadata_ordered_dict(clinvar_keys, metadata)

            names, statuses, significances = (
                (entry.replace('|', ',').split(',') if entry else None)
                for entry in
                (
                    clinvar_entry[key]
                    for key in ('CLNDBN', 'CLNREVSTAT', 'CLNSIG')
                )
            )

            # those length should be always equal if they exists
            sub_entries_cnt = max(
                [
                    len(x)
                    for x in (names, statuses, significances)
                    if x
                ] or [0]
            )

            at_least_one_significant_sub_entry = False

            for i in range(sub_entries_cnt):

                try:
                    if names:
                        if names[i] not in ('not_specified', 'not_provided'):
                            names[i] = self._beautify_disease_name(names[i])
                            at_least_one_significant_sub_entry = True
                    if statuses and statuses[i] == 'no_criteria':
                        statuses[i] = None
                except IndexError:
                    print('Malformed row (wrong count of subentries) on %s-th entry:' % i)
                    print(line)
                    return False

            values = list(clinvar_entry.values())

            # following 2 lines are result of issue #47 - we don't import those
            # clinvar mutations that do not have any diseases specified:
            if not at_least_one_significant_sub_entry:
                return

            for mutation_id in self.preparse_mutations(line):

                # take care of duplicates
                duplicated = self.look_after_duplicates(mutation_id, clinvar_mutations, values[:4])
                if duplicated:
                    duplicates += 1
                    continue

                # take care of nearly-duplicates
                same_mutation_pointers = self.mutations_details_pointers_grouped_by_unique_mutations[mutation_id]
                assert len(same_mutation_pointers) <= 1
                if same_mutation_pointers:
                    pointer = same_mutation_pointers[0]
                    old = self.data_as_dict(clinvar_mutations[pointer])
                    new = self.data_as_dict(values, mutation_id=mutation_id)

                    if old['db_snp_ids'] != [new['db_snp_ids']]:
                        clinvar_mutations[pointer][1].append(new['db_snp_ids'])

                    # if either of the dbSNP entries is validated, the mutation is validated
                    # (the same with presence in PubMed)
                    for key in ['is_validated', 'is_in_pubmed_central']:
                        if old[key] != new[key] and new[key]:
                            index = self.insert_keys.index(key)
                            clinvar_mutations[pointer][index] = True

                    print(
                        'Merged details referring to the same mutation (%s): %s into %s'
                        %
                        (mutation_id, values, clinvar_mutations[pointer])
                    )
                    continue

                self.protect_from_duplicates(mutation_id, clinvar_mutations)

                # Python 3.5 makes it easy: **values (but is not available)
                clinvar_mutations.append(
                    [
                        mutation_id,
                        [values[0]],
                        values[1],
                        values[2],
                        values[3],
                    ]
                )

                for i in range(sub_entries_cnt):
                    # disease names matching is case insensitive;
                    # NB: MySQL uses case-insensitive unique constraint by default
                    name = names[i]
                    key = name.lower()

                    # we don't want _uninteresting_ data
                    if name in ('not_specified', 'not provided'):
                        continue

                    if key in new_diseases:
                        disease_id, recorded_name = new_diseases[key]
                        if recorded_name != name:
                            print(f'Note: {name} and {recorded_name} diseases were merged')
                    else:
                        try:
                            disease = Disease.query.filter(Disease.name.ilike(name)).one()
                            recorded_name = disease.name
                            disease_id = disease.id
                            if recorded_name != name:
                                print(f'Note: {name} and {recorded_name} diseases were merged')
                        except NoResultFound:
                            highest_disease_id += 1
                            new_diseases[key] = highest_disease_id, name
                            disease_id = highest_disease_id

                    clinvar_data.append(
                        (
                            len(clinvar_mutations),
                            int(significances[i]) if significances is not None else None,
                            disease_id,
                            statuses[i] if statuses else None,
                        )
                    )

        parse_tsv_file(
            path,
            clinvar_parser,
            self.header,
            file_opener=gzip_open_text
        )

        print('%s duplicates found' % duplicates)

        return clinvar_mutations, clinvar_data, new_diseases.values()

    def export_details_headers(self):
        return ['disease']

    def export_details(self, mutation):
        return [
            [d.disease_name]
            for d in mutation.clin_data
        ]

    def insert_details(self, details):
        clinvar_mutations, clinvar_data, new_diseases = details

        bulk_orm_insert(
            Disease,
            ('name',),
            [(disease,) for pk, disease in new_diseases]
        )
        self.insert_list(clinvar_mutations)
        bulk_orm_insert(
            ClinicalData,
            (
                'inherited_id',
                'sig_code',
                'disease_id',
                'rev_status',
            ),
            clinvar_data
        )

    def restart_autoincrement(self, model):
        assert self.model == model
        for model in [self.model, ClinicalData, Disease]:
            restart_autoincrement(model)
            db.session.commit()

    def raw_delete_all(self, model):
        assert self.model == model

        # remove clinical data
        data_cnt = ClinicalData.query.delete()

        # remove diseases
        disease_cnt = Disease.query.delete()

        print('%s diseases and %s clinical data entries removed' % (disease_cnt, data_cnt))

        # then mutations
        count = self.model.query.delete()

        # count of removed mutations is more informative
        return count
