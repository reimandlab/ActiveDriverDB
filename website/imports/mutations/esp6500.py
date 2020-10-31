from models import ExomeSequencingMutation
from helpers.parsers import tsv_file_iterator
from helpers.parsers import gzip_open_text

from .mutation_importer import MutationImporter


class ESP6500Importer(MutationImporter):

    name = 'esp6500'
    model = ExomeSequencingMutation
    default_path = 'data/mutations/ESP6500_muts_annotated.txt.gz'
    header = [
        'Chr', 'Start', 'End', 'Ref', 'Alt', 'Func.refGene', 'Gene.refGene',
        'GeneDetail.refGene', 'ExonicFunc.refGene', 'AAChange.refGene', 'V11',
        'V12', 'V13', 'V14', 'V15', 'V16', 'V17', 'V18', 'V19', 'V20', 'V21'
    ]
    insert_keys = ('mutation_id', 'maf_ea', 'maf_aa', 'maf_all')

    def iterate_lines(self, path):
        return tsv_file_iterator(path, self.header, file_opener=gzip_open_text)

    def parse_metadata(self, line):
        metadata = line[20].split(';')

        # not flexible way to select MAF from metadata, but quite quick
        assert metadata[4].startswith('MAF=')

        maf_ea, maf_aa, maf_all = map(float, metadata[4][4:].split(','))
        return maf_ea, maf_aa, maf_all

    def test_line(self, line):
        maf_ea, maf_aa, maf_all = self.parse_metadata(line)
        return maf_all

    def parse(self, path):
        esp_mutations = []
        duplicates = 0
        skipped = 0

        def esp_parser(line):
            nonlocal duplicates, skipped

            maf_ea, maf_aa, maf_all = self.parse_metadata(line)

            if maf_all == 0:
                skipped += 1
                return

            for mutation_id in self.get_or_make_mutations(line):

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

        for line in self.iterate_lines(path):
            esp_parser(line)

        print(f'{duplicates} duplicates found')
        print(f'{skipped} zero-frequency mutations skipped')

        return esp_mutations

    def insert_details(self, esp_mutations):
        self.insert_list(esp_mutations)

    def export_details_headers(self):
        return ['maf_ea', 'maf_aa', 'maf_all']

    def export_details(self, mutation):
        return [
            [
                str(getattr(mutation, attr))
                for attr in self.export_details_headers()
            ]
        ]
