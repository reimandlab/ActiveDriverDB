from models import MC3Mutation
from .tcga import TCGAImporter


def load_tss_cancer_map(tss_cancer_map_path):
    """
    Return Tissue Source Site (TSS) id: associated cancer mapping as derived from:
    https://gdc.cancer.gov/resources-tcga-users/tcga-code-tables/tissue-source-site-codes
    (wiki.nci.nih.gov/pages/viewpage.action?pageId=29557833 is obsolete)

    Args:
        tss_cancer_map_path: path to tab-separated file with tss: cancer map

    Returns:
        A dictionary of tss: cancer name mappings.

    """
    tss_dict = {}
    with open(tss_cancer_map_path) as f:
        for line in f:
            tss_code, cancer_study = line.split('\t')
            tss_dict[tss_code] = cancer_study.strip()
    return tss_dict


class MC3Importer(TCGAImporter):

    name = 'mc3'
    model = MC3Mutation
    default_path = 'data/mutations/mc3_muts_annotated.txt.gz'
    # ['Chr', 'Start', 'End', 'Ref', 'Alt', 'Func.refGene', 'Gene.refGene',
    # 'GeneDetail.refGene', 'ExonicFunc.refGene', 'AAChange.refGene', 'Tumor_Sample_Barcode']
    header = None
    tss_cancer_map_path = 'data/mutations/tissue_source_site_codes.tsv'

    def extract_cancer_name(self, sample_name):
        tss_code = sample_name.split('-')[1]
        return self.cancer_barcodes[tss_code]

    def decode_line(self, line):
        sample_name = line[10]
        cancer_name = self.extract_cancer_name(sample_name)
        return cancer_name, sample_name

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cancer_barcodes = load_tss_cancer_map(self.tss_cancer_map_path)

    def parse(self, path):
        from stats import hypermutated_samples

        print(
            'Analyzing data to find hypermutated samples '
            '(samples with > 900 mutations - i.e. roughly 30 muts/megabase)'
        )
        hypermutated = hypermutated_samples(path)
        self.samples_to_skip = set(hypermutated.keys())
        hypermutated_count = len(self.samples_to_skip)
        print(f'{hypermutated_count} samples are hypermutated and will be skipped at import.')

        return super().parse(path)
