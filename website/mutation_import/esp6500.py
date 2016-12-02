from models import ExomeSequencingMutation
from import_mutations import MutationImporter
from helpers.parsers import parse_tsv_file
import gzip


class Importer(MutationImporter):

    model = ExomeSequencingMutation
    default_path = 'data/mutations/ESP6500_muts_annotated.txt.gz'
    header = [
        'Chr', 'Start', 'End', 'Ref', 'Alt', 'Func.refGene', 'Gene.refGene',
        'GeneDetail.refGene', 'ExonicFunc.refGene', 'AAChange.refGene', 'V11',
        'V12', 'V13', 'V14', 'V15', 'V16', 'V17', 'V18', 'V19', 'V20', 'V21'
    ]
    insert_keys = ('maf_ea', 'maf_aa', 'maf_all', 'mutation_id')

    def parse(self, path):
        esp_mutations = []

        def esp_parser(line):

            metadata = line[20].split(';')

            # not flexible way to select MAF from metadata, but quite quick
            assert metadata[4].startswith('MAF=')

            maf_ea, maf_aa, maf_all = map(float, metadata[4][4:].split(','))

            for mutation_id in self.preparse_mutations(line):

                esp_mutations.append(
                    (
                        maf_ea,
                        maf_aa,
                        maf_all,
                        mutation_id
                    )
                )

        parse_tsv_file(path, esp_parser, self.header, file_opener=gzip.open)

        return esp_mutations

    def insert_details(self, esp_mutations):
        self.insert_list(esp_mutations)
