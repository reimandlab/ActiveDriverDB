from models import ExomeSequencingMutation
from imports.mutations import MutationImporter
from helpers.parsers import parse_tsv_file
from helpers.parsers import gzip_open_text


class Importer(MutationImporter):

    model = ExomeSequencingMutation
    default_path = 'data/mutations/ESP6500_muts_annotated.txt.gz'
    header = [
        'Chr', 'Start', 'End', 'Ref', 'Alt', 'Func.refGene', 'Gene.refGene',
        'GeneDetail.refGene', 'ExonicFunc.refGene', 'AAChange.refGene', 'V11',
        'V12', 'V13', 'V14', 'V15', 'V16', 'V17', 'V18', 'V19', 'V20', 'V21'
    ]
    insert_keys = ('mutation_id', 'maf_ea', 'maf_aa', 'maf_all')

    def parse(self, path):
        esp_mutations = []
        duplicates = 0
        skipped = 0

        def esp_parser(line):
            nonlocal duplicates, skipped

            metadata = line[20].split(';')

            # not flexible way to select MAF from metadata, but quite quick
            assert metadata[4].startswith('MAF=')

            maf_ea, maf_aa, maf_all = map(float, metadata[4][4:].split(','))

            if maf_all == 0:
                skipped += 1
                return

            for mutation_id in self.preparse_mutations(line):

                values = (
                    mutation_id,
                    maf_ea,
                    maf_aa,
                    maf_all
                )

                duplicated = self.look_after_duplicates(mutation_id, esp_mutations, values)
                if duplicated:
                    duplicates += 1
                    continue

                self.protect_from_duplicates(mutation_id, esp_mutations)

                esp_mutations.append(values)

        parse_tsv_file(
            path, esp_parser,
            self.header,
            file_opener=gzip_open_text
        )

        print('%s duplicates found' % duplicates)
        print('%s zero-frequency mutations skipped' % skipped)

        return esp_mutations

    def insert_details(self, esp_mutations):
        self.insert_list(esp_mutations)
