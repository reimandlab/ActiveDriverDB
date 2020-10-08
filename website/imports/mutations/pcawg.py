from models import PCAWGMutation
from .tcga import TCGAImporter


class PCAWGImporter(TCGAImporter):

    name = 'pcawg'
    model = PCAWGMutation
    default_path = 'data/mutations/pcawg_muts_annotated.txt.gz'
    # ['Chr', 'Start', 'End', 'Ref', 'Alt', 'Func.refGene', 'Gene.refGene',
    # 'GeneDetail.refGene', 'ExonicFunc.refGene', 'AAChange.refGene',
    # 'patient', 'cancer', 'tag']
    header = None

    def decode_line(self, line):
        cancer_name = line[10]
        patient_id = line[11]
        return cancer_name, patient_id

    def parse(self, path):
        from stats import hypermutated_samples

        print(
            'Analyzing data to find hypermutated samples '
            '(samples with > 900 mutations - i.e. roughly 30 muts/megabase)'
        )
        hypermutated = hypermutated_samples(path, sample_column=11)
        self.samples_to_skip = set(hypermutated.keys())
        hypermutated_count = len(self.samples_to_skip)
        print(f'{hypermutated_count} samples are hypermutated and will be skipped at import.')

        return super().parse(path)

