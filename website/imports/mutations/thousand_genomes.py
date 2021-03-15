from os.path import basename, dirname

from models import The1000GenomesMutation
from helpers.parsers import read_from_gz_files

from .mutation_importer import MutationImporter
from .mutation_importer.helpers import make_metadata_ordered_dict


class The1000GenomesImporter(MutationImporter):

    name = 'thousand_genomes'
    model = The1000GenomesMutation
    default_path = 'data/mutations/G1000/G1000_chr*.txt.gz'
    insert_keys = (
        'mutation_id',
        'maf_all',
        'maf_eas',
        'maf_amr',
        'maf_afr',
        'maf_eur',
        'maf_sas',
    )

    @staticmethod
    # TODO: there are some issues with this function
    def find_af_subfield_number(line):
        """Get subfield number in 1000 Genomes VCF-originating metadata,

        where allele frequencies for given mutations are located.

        Example record:
        # noqa: E501
        10	73567365	73567365	T	C	exonic	CDH23	.	nonsynonymous SNV	CDH23:NM_001171933:exon12:c.T1681C:p.F561L,CDH23:NM_001171934:exon12:c.T1681C:p.F561L,CDH23:NM_022124:exon57:c.T8401C:p.F2801L	0.001398	100	20719	10	73567365	rs3802707	TC,G	100	PASS	AC=2,5;AF=0.000399361,0.000998403;AN=5008;NS=2504;DP=20719;EAS_AF=0.001,0.005;AMR_AF=0,0;AFR_AF=0,0;EUR_AF=0,0;SAS_AF=0.001,0;AA=T|||;VT=SNP;MULTI_ALLELIC;EX_TARGET	GT
        There are AF metadata for two different mutations: T -> TC and T -> G.
        The mutation which we are currently analysing is T -> C

        Look for fields 3 and 4; 4th field is sufficient to determine mutation.
        """
        dna_mut = line[4]
        return [seq[0] for seq in line[17].split(',')].index(dna_mut)

    def iterate_lines(self, path):
        for line in read_from_gz_files(
                dirname(path),
                basename(path),
                skip_header=False
        ):
            yield line.rstrip().split('\t')

    maf_keys = (
        'AF',
        'EAS_AF',
        'AMR_AF',
        'AFR_AF',
        'EUR_AF',
        'SAS_AF',
    )

    def parse_metadata(self, line):
        metadata = line[20].split(';')

        maf_data = make_metadata_ordered_dict(
            self.maf_keys,
            metadata,
            self.find_af_subfield_number(line)
        )
        return maf_data

    def test_line(self, line):
        maf_data = self.parse_metadata(line)
        return maf_data['AF'] != '0'

    def parse(self, path):
        thousand_genomes_mutations = []
        duplicates = 0
        skipped = 0

        for line in self.iterate_lines(path):

            maf_data = self.parse_metadata(line)

            # ignore mutations with frequency equal to zero
            if maf_data['AF'] == '0':
                skipped += 1
                continue

            values = list(maf_data.values())

            for mutation_id in self.get_or_make_mutations(line):

                duplicated = self.look_after_duplicates(mutation_id, thousand_genomes_mutations, values)
                if duplicated:
                    duplicates += 1
                    continue

                self.protect_from_duplicates(mutation_id, thousand_genomes_mutations)

                thousand_genomes_mutations.append(
                    (mutation_id, *values)
                )

        print(f'{duplicates} duplicates found')
        print(f'{skipped} zero-frequency mutations skipped')

        return thousand_genomes_mutations

    def insert_details(self, thousand_genomes_mutations):
        self.insert_list(thousand_genomes_mutations)

    def export_genomic_clean_fields(self, fields):
        return fields[:12]

    def export_details_headers(self):
        return [
            'maf_all',
            'maf_eas',
            'maf_amr',
            'maf_afr',
            'maf_eur',
            'maf_sas',
        ]

    def export_details(self, mutation):
        return [
            [
                str(getattr(mutation, attr))
                for attr in self.export_details_headers()
            ]
        ]
