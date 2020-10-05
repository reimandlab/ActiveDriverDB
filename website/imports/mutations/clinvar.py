import re
from collections import defaultdict
from typing import Mapping, Iterable

from sqlalchemy.orm.exc import NoResultFound
from models import InheritedMutation, Disease
from models import ClinicalData, or_
from helpers.parsers import tsv_file_iterator
from helpers.parsers import gzip_open_text
from database.bulk import get_highest_id, bulk_orm_insert, restart_autoincrement
from database import db

from .mutation_importer import MutationImporter
from .mutation_importer.helpers import make_metadata_ordered_dict


class MalformedRawError(Exception):
    pass


class ClinVarImporter(MutationImporter):

    name = 'clinvar'
    model = InheritedMutation
    default_path = 'data/mutations/clinvar_muts_annotated.txt.gz'
    default_xml_path = 'data/mutations/ClinVarFullRelease_2020-10.xml.gz'
    header = [
        'Chr', 'Start', 'End', 'Ref', 'Alt', 'Func.refGene', 'Gene.refGene',
        'GeneDetail.refGene', 'ExonicFunc.refGene', 'AAChange.refGene', 'Otherinfo',
    ]
    insert_keys = (
        'mutation_id',
        'db_snp_ids',
        'combined_significances',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.xml_path = None
        self.skipped_significances = defaultdict(int)

    def load(self, path=None, update=False, clinvar_xml_path=None, **ignored_kwargs):
        print(
            'Please note that the annovar and XML database needs to be based on the same ClinVar release'
            ' to avoid incorrect removal of variants which are missing metadata (i.e. not found in the XML file)'
        )
        self.xml_path = clinvar_xml_path or self.default_xml_path
        super().load(path, update, **ignored_kwargs)

    @staticmethod
    def _beautify_disease_name(name):
        if '___' in name:
            # for edge cases use a robust regexpr
            name = re.sub('([^_])_([^_])', r'\1 \2', name).replace('___', ' _ ')
        else:
            # but for 99% of data, simple .replace() is much faster:
            name = name.replace('_', ' ')
        return name.replace('%3B', ';')

    def iterate_lines(self, path):
        return tsv_file_iterator(path, self.header, file_opener=gzip_open_text)

    def test_line(self, line):
        try:
            at_least_one_significant_sub_entry, *args = self.parse_metadata(line)
            return at_least_one_significant_sub_entry
        except MalformedRawError:
            return False

    clinvar_keys = (
        'RS',
        'CLNDISDB',
        'CLNDN',
        'CLNSIG',
        'CLNSIGCONF'
    )

    disease_id_clinvar_to_db = {
        'MedGen': 'medgen_id',
        'OMIM': 'omim_id',
        'SNOMED_CT': 'snomed_ct_id',
        'Orphanet': 'orhpanet_id',
        'Human_Phenotype_Ontology': 'hpo_id'
    }

    inverse_significance_map: Mapping[str, int] = {
        name.lower(): code
        for code, name in ClinicalData.significance_codes.items()
    }

    significance_map = {
        'pathologic': 'pathogenic',
        'probable-pathogenic': 'likely pathogenic',
        'cancer': 'pathogenic',
        'untested': 'not provided',
        'variant of unknown significance': 'uncertain significance',
        'uncertain': 'uncertain significance',
        'drug-response': 'drug response',
        'probable-non-pathogenic': 'likely benign',
        'probably not pathogenic': 'likely benign',
        'non-pathogenic': 'benign',
    }

    def parse_significance(self, significance):

        significance = significance.lower()

        if significance in self.significance_map:
            significance = self.significance_map[significance]

        additional_significances = []

        if significance not in self.inverse_significance_map:
            assign_to = 'other'

            first_significance, *additional_significances = significance.split(',')

            if first_significance in self.inverse_significance_map:
                assign_to = first_significance

            if significance not in self.skipped_significances:
                print(f'Unmapped significance status: "{significance}", assigning "{assign_to}"')

            self.skipped_significances[significance] += 1

            significance = assign_to

        sig_code = self.inverse_significance_map[significance]

        return sig_code, [sig.strip() for sig in additional_significances]

    def import_disease_associations(self):
        """Add disease association details to the already imported mutation-disease associations"""
        from xml.etree import ElementTree
        from tqdm import tqdm
        import gzip

        ignored_traits = {
            'not specified',
            'not provided'
        }
        accepted_assertions = {
            'variation to disease',
            'variation in modifier gene to disease',
            'variation to included disease',
            'confers sensitivity'
        }

        print('Only including assertions: ', accepted_assertions)
        print('Ignoring traits: ', ignored_traits)

        self.skipped_significances = defaultdict(int)

        accepted_species = {'Human', 'human'}
        skipped_species = set()

        skipped_variation_types = set()
        conflicting_types = set()
        skipped_diseases = set()

        variants_of_interest = {
            variation_id
            for variation_id, in db.session.query(ClinicalData.variation_id)
        }

        # otherwise there is no point...
        assert variants_of_interest

        opener = gzip.open if self.xml_path.endswith('.gz') else open

        total_size = 0
        with opener(self.xml_path) as clinvar_full_release:
            for line in clinvar_full_release:
                total_size += len(line)

        step = 0

        with opener(self.xml_path) as clinvar_full_release:
            tree = iter(ElementTree.iterparse(clinvar_full_release, events=('start', 'end')))
            event, root = next(tree)

            progress_bar = tqdm(total=1000)
            last_progress = 0

            for event, element in tree:
                if event != 'end' or element.tag != 'ClinVarSet':
                    continue

                reference = element.find('ReferenceClinVarAssertion')

                assertion = reference.find('Assertion').attrib['Type']

                # This skips over "confers resistance" and "variant to named protein"
                if assertion not in accepted_assertions:
                    assert assertion in {'confers resistance', 'variant to named protein'}
                    continue

                # variant-disease accession
                rcv_accession = reference.find('ClinVarAccession')
                assert rcv_accession.attrib['Type'] == 'RCV'

                # rcv_accession = rcv_accession.attrib['Acc']

                # variation or variation set, corresponds to InheritedMutation in our database
                variation_set = reference.find('MeasureSet')

                # Note: this skips over minority of records with "GenotypeSet"s
                if not variation_set:
                    assert reference.find('GenotypeSet')
                    continue

                # skip over haplotypes, etc
                variation_set_type = variation_set.attrib['Type']
                if variation_set_type != 'Variant':
                    assert variation_set_type in {'Haplotype', 'Distinct chromosomes', 'Phase unknown'}
                    continue

                # corresponds to InheritedMutation.variation_id
                variation_id = int(variation_set.attrib['ID'])

                if variation_id not in variants_of_interest:
                    # as we effectively have only a fraction of all variations
                    # (non-synonymous SNVs only), this will speed things up
                    continue

                sample = reference.find('ObservedIn/Sample')
                species = sample.find('Species').text

                if species not in accepted_species:
                    if species not in skipped_species:
                        print(f'Skipping non-human species: "{species}"')
                        skipped_species.add(species)
                    continue

                origin = sample.find('Origin').text

                assert reference.find('RecordStatus').text == 'current'

                variations = variation_set.findall('Measure')
                assert len(variations) == 1

                variation = variations[0]

                variation_type = variation.attrib['Type']
                if variation_type != 'single nucleotide variant':
                    if variation_type not in skipped_variation_types:
                        print(f'Skipping variation type: {variation_type}')
                        skipped_variation_types.add(variation_type)

                # Disease or observation, corresponds to Disease
                trait = reference.find('TraitSet')
                trait_type = trait.attrib['Type']
                trait_name = trait.find('Trait/Name/ElementValue').text

                if trait_name in ignored_traits:
                    continue

                try:
                    disease = Disease.query.filter_by(name=trait_name).one()
                except NoResultFound:
                    resolved = False
                    if 'Mucolipidosis, Type' in trait_name:
                        print(f'Working around changed name for {trait_name}')
                        trait_name = trait_name.replace('Mucolipidosis, Type', 'Mucolipidosis')
                        try:
                            disease = Disease.query.filter_by(name=trait_name).one()
                            resolved = True
                        except NoResultFound:
                            pass

                    if not resolved:
                        skipped_diseases.add(trait_name)
                        print(f'Disease "{trait_name}" entry not found, skipping')
                        continue

                if disease.clinvar_type:
                    if disease.clinvar_type != trait_type:
                        if disease.name not in conflicting_types:
                            conflicting_types.add(disease.name)
                            action = ''
                            if trait_type == 'Disease':
                                disease.clinvar_type = trait_type
                                action = ': overwriting the old type with "Disease"'
                            print(f'Conflicting trait types for "{disease.name}": "{disease.clinvar_type}" != "{trait_type}"{action}')
                else:
                    disease.clinvar_type = trait_type

                significance_annotations = reference.findall('ClinicalSignificance')

                assert len(significance_annotations) == 1

                significance_annotation = significance_annotations[0]

                significance = significance_annotation.find('Description').text
                review_status = significance_annotation.find('ReviewStatus').text

                sig_code, additional_significances = self.parse_significance(significance)

                disease_associations: Iterable[ClinicalData] = (
                    ClinicalData.query
                    .filter(ClinicalData.disease == disease)
                    .filter(ClinicalData.variation_id == variation_id)
                )

                association_values = {
                    'sig_code': sig_code,
                    'rev_status': review_status,
                    'origin': origin
                }

                for disease_association in disease_associations:

                    for key, value in association_values.items():
                        old_value = getattr(disease_association, key)
                        if old_value and old_value != value:
                            print(
                                f'Warning: {key} was already set to {old_value} for {variation_id}/{disease},'
                                f'while the new value is {value} (accession: {rcv_accession})'
                            )

                    disease_association.sig_code = sig_code
                    disease_association.rev_status = review_status
                    # IMPORTANT: every "continue" up to this point means that the mutation
                    # will be removed in remove_muts_without_origin(), because origin will not be set
                    disease_association.origin = origin

                    if additional_significances:
                        disease_association.additional_significances = set(additional_significances)

                element.clear()

                step += 1

                if step % 550 == 0:
                    progress = int(clinvar_full_release.tell() / total_size * 1000)

                    if progress != last_progress:
                        progress_bar.update(progress - last_progress)
                        last_progress = progress

                    root.clear()

        print(skipped_diseases)
        print(self.skipped_significances)
        db.session.commit()

    def remove_muts_without_origin(self):

        origin_exclusion_list = {
            'not applicable',
            'not provided',
            'not-reported',
            'somatic',
            'tested-inconclusive',
            'unknown'
        }

        print('ClinVar mutations origin exclusion list: ', origin_exclusion_list)

        print('Removing ClinVar associations with blacklisted or missing origin; NOTE:')
        print('\torigin is not set also when the mutation was skipped due to other reasons, such as non-human species')
        removed_cnt = ClinicalData.query.filter(
            or_(ClinicalData.origin == None, ClinicalData.origin.in_(origin_exclusion_list))
        ).delete(synchronize_session='fetch')
        db.session.commit()
        print(f'Removed {removed_cnt} associations')

        print('Removing orphaned ClinVar mutations (with no associations)')
        empty_mutations_cnt = InheritedMutation.query.filter(~InheritedMutation.clin_data.any()).delete(
            synchronize_session='fetch'
        )
        db.session.commit()
        print(f'Removed {empty_mutations_cnt} ClinVar mutations without associations')

        print('Removing diseases without associations...')
        removed_diseases = Disease.query.filter(~Disease.associations.any()).delete(synchronize_session='fetch')
        print(f'removing {removed_diseases} diseases')
        db.session.commit()

    def _load(self, path, update, **kwargs):
        skip_removal = kwargs.pop('skip_removal', False)
        super()._load(path, update, **kwargs)
        self.import_disease_associations()
        if not skip_removal:
            self.remove_muts_without_origin()

    def parse_metadata(self, line):
        metadata = line[20].split(';')

        clinvar_entry = make_metadata_ordered_dict(self.clinvar_keys, metadata)

        disease_names, diseases_ids, combined_significances, significances_set = (
            (entry.split('|') if entry else [])
            for entry in
            (
                clinvar_entry[key]
                for key in ('CLNDN', 'CLNDISDB', 'CLNSIG', 'CLNSIGCONF')
            )
        )

        diseases_ids_map = [
            {
                key: ':'.join(values)
                # needed as some ids have colons inside, e.g.:
                # CLNDISDB=Human_Phenotype_Ontology:HP:0002145
                for disease_id in disease_ids.split(',')
                for key, *values in [disease_id.split(':')]
            }
            for disease_ids in diseases_ids
        ]
        diseases_ids = [
            [
                disease_ids_map.get(disease_id_clinvar, None)
                for disease_id_clinvar in self.disease_id_clinvar_to_db
            ]
            for disease_ids_map in diseases_ids_map
        ]

        combined_significances = [
            significance.replace('_', ' ')
            for significance in combined_significances
        ]

        assert len(combined_significances) <= 1
        assert not significances_set or len(significances_set) == 1

        # those lengths should be always equal
        assert len(diseases_ids) == len(disease_names)

        sub_entries_cnt = len(disease_names)
        at_least_one_meaningful_sub_entry = False

        for i in range(sub_entries_cnt):

            try:
                if disease_names:
                    if disease_names[i] not in ('not_specified', 'not_provided'):
                        disease_names[i] = self._beautify_disease_name(disease_names[i])
                        at_least_one_meaningful_sub_entry = True
            except IndexError:
                raise MalformedRawError(f'Malformed row (wrong count of sub-entries) on {i}-th entry:')

        variation_id = int(line[15])

        return (
            at_least_one_meaningful_sub_entry, clinvar_entry, sub_entries_cnt,
            disease_names, diseases_ids, combined_significances, variation_id
        )

    @classmethod
    def compare_ids(cls, recorded_ids, recorded_name, disease_ids, name):
        """recorded = old"""
        out = None
        different_ids = [
            id_label
            for i, (id_label, id_name) in enumerate(cls.disease_id_clinvar_to_db.items())
            if str(recorded_ids[i]) != str(disease_ids[i])
        ]
        if any(different_ids):
            new_ids = dict(zip(cls.disease_id_clinvar_to_db, disease_ids))
            old_ids = dict(zip(cls.disease_id_clinvar_to_db, recorded_ids))
            different_ids_values = ', '.join([
                f'{id_label}: {old_ids[id_label]} (old) vs {new_ids[id_label]} (new)'
                for id_label in different_ids
            ])
            same_ids_labels = ', '.join(
                f'{id_label} ({old_ids[id_label]})'
                for id_label in cls.disease_id_clinvar_to_db
                if id_label not in different_ids and old_ids[id_label]
            )
            out = (
                f'Note: {name} identifiers differ from {recorded_name} identifiers'
                f' {different_ids_values}. The following remain the same: {same_ids_labels}.'
            )
        # not all ids differ (at least some are the same)
        assert len(different_ids) != len(recorded_ids)

        return out, different_ids

    def parse(self, path):
        clinvar_mutations = []
        clinvar_data = []
        duplicates = 0
        new_diseases = {}

        highest_disease_id = get_highest_id(Disease)

        def clinvar_parser(line):
            nonlocal highest_disease_id, duplicates

            try:
                (
                    at_least_one_significant_sub_entry, clinvar_entry, sub_entries_cnt,
                    disease_names, diseases_ids, combined_significances, variation_id
                ) = self.parse_metadata(line)
            except MalformedRawError as e:
                print(str(e) + '\n', line)
                return False

            # following 2 lines are result of issue #47 - we don't import those
            # clinvar mutations that do not have any diseases specified:
            if not at_least_one_significant_sub_entry:
                return

            values = list(clinvar_entry.values())

            # should correspond to insert keys!
            clinvar_mutation_values = [
                {int(rs) for rs in (clinvar_entry['RS'] or '').split('|') if rs},
                set(combined_significances)
            ]

            for mutation_id in self.get_or_make_mutations(line):

                # take care of duplicates
                duplicated = self.look_after_duplicates(mutation_id, clinvar_mutations, values[:1])
                if duplicated:
                    duplicates += 1
                    continue

                # take care of nearly-duplicates
                same_mutation_pointers = self.mutations_details_pointers_grouped_by_unique_mutations[mutation_id]
                assert len(same_mutation_pointers) <= 1

                if same_mutation_pointers:
                    pointer = same_mutation_pointers[0]
                    retained_values = clinvar_mutations[pointer]
                    old = self.data_as_dict(retained_values)
                    new = self.data_as_dict(clinvar_mutation_values, mutation_id=mutation_id)

                    for key in ['db_snp_ids', 'combined_significances']:
                        index = self.insert_keys.index(key)
                        retained_values[index].update(new[key])

                    print(f'Merged SNVs of the same protein mutation ({mutation_id}):\n\t{new}\nand\n\t{old}\n')
                else:
                    # only add the protein-level mutation once
                    self.protect_from_duplicates(mutation_id, clinvar_mutations)
                    clinvar_mutations.append([mutation_id, *clinvar_mutation_values])

                # then add the disease-mutation relations;
                # if these are caused by multiple SNVs (and thus have different variant_id),
                # add them for each of SNVs separately as each can have different sig_code:

                for i in range(sub_entries_cnt):
                    # disease names matching is case insensitive;
                    # NB: MySQL uses case-insensitive unique constraint by default
                    name = disease_names[i]
                    disease_ids = diseases_ids[i]
                    key = name.lower()
                    merged = False

                    # we don't want _uninteresting_ data
                    if name in ('not_specified', 'not_provided'):
                        continue

                    if key in new_diseases:
                        disease_id, (recorded_name, *recorded_ids) = new_diseases[key]
                        merged = True
                        disease = None
                    else:
                        try:
                            disease = Disease.query.filter(Disease.name.ilike(name)).one()
                            disease_id = disease.id
                            recorded_name = disease.name
                            recorded_ids = [
                                getattr(disease, id_name, None)
                                for id_name in self.disease_id_clinvar_to_db.values()
                            ]
                            merged = True
                        except NoResultFound:
                            highest_disease_id += 1
                            new_diseases[key] = highest_disease_id, (name, *disease_ids)

                            disease_id = highest_disease_id

                    if merged:
                        if recorded_name != name:
                            print(
                                f'Note: {name} and {recorded_name} diseases were merged'
                                f' (identical in case-insensitive comparison)'
                            )
                        notice, different_ids = self.compare_ids(recorded_ids, recorded_name, disease_ids, name)
                        if notice:
                            print(notice)
                        if different_ids:
                            if disease:
                                new_ids = dict(zip(self.disease_id_clinvar_to_db, disease_ids))
                                for id_to_update in different_ids:
                                    setattr(disease, id_to_update, new_ids[id_to_update])
                                print(f'The ids of the {recorded_name} were updated.')
                            else:
                                print(
                                    'No ids updates were performed as the ids came from newly added disease;'
                                    ' this might be a ClinVar integrity issue.'
                                )

                    clinvar_data.append(
                        (
                            len(clinvar_mutations),
                            disease_id,
                            variation_id
                        )
                    )

        for line in self.iterate_lines(path):
            clinvar_parser(line)

        print(f'{duplicates} duplicates found')

        return clinvar_mutations, clinvar_data, new_diseases.values()

    def export_details_headers(self):
        return ['disease', 'significance', 'has_significance_conflict']

    def export_details(self, mutation):
        return [
            [d.disease_name, d.significance or '', str(d.has_significance_conflict)]
            for d in mutation.clin_data
        ]

    def insert_details(self, details):
        clinvar_mutations, clinvar_data, new_diseases = details

        disease_columns = ('name', *self.disease_id_clinvar_to_db.values())

        bulk_orm_insert(
            Disease,
            disease_columns,
            [disease_data for pk, disease_data in new_diseases]
        )
        self.insert_list(clinvar_mutations)
        bulk_orm_insert(
            ClinicalData,
            ('inherited_id', 'disease_id', 'variation_id'),
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

        print(f'{disease_cnt} diseases and {data_cnt} clinical data entries removed')

        # then mutations
        count = self.model.query.delete()

        # count of removed mutations is more informative
        return count
