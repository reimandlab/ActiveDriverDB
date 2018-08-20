from collections import defaultdict
from database import db
from database import get_or_create
from models import Cancer
from models import TCGAMutation
from imports.mutations import MutationImporter
from helpers.parsers import iterate_tsv_gz_file
from helpers.parsers import chunked_list
from sqlalchemy.orm.exc import NoResultFound


class Importer(MutationImporter):

    model = TCGAMutation
    default_path = 'data/mutations/TCGA_muts_annotated.txt.gz'
    header = [
        'Chr', 'Start', 'End', 'Ref', 'Alt', 'Func.refGene', 'Gene.refGene',
        'GeneDetail.refGene', 'ExonicFunc.refGene', 'AAChange.refGene', 'V11'
    ]
    export_samples = False
    samples_to_skip = set()

    def decode_line(self, line):
        assert line[10].startswith('comments: ')
        cancer_name, sample_name, _ = line[10][10:].split(';')
        return cancer_name, sample_name

    def iterate_lines(self, path):
        return iterate_tsv_gz_file(path, file_header=self.header)

    def test_line(self, line):
        cancer_name, sample_name = self.decode_line(line)
        return sample_name not in self.samples_to_skip

    def parse(self, path):

        mutations = defaultdict(lambda: [0, set()])

        for line in self.iterate_lines(path):
            cancer_name, sample_name = self.decode_line(line)

            if sample_name in self.samples_to_skip:
                continue

            cancer, created = get_or_create(Cancer, name=cancer_name)

            if created:
                db.session.add(cancer)

            for mutation_id in self.get_or_make_mutations(line):

                key = (mutation_id, cancer.id)

                mutations[key][0] += 1
                mutations[key][1].add(sample_name)

        return mutations

    def create_init_kwargs(self, mutation, data):
        return {
            'mutation_id': mutation[0],
            'cancer_id': mutation[1],
            'samples': ','.join(data[1]),
            'count': data[0]
        }

    def export_details_headers(self):
        if self.export_samples:
            return ['cancer_type', 'sample_id']
        return ['cancer_type']

    def export_details(self, mutation):
        if self.export_samples:
            return [
                [mutation.cancer.code, sample]
                for sample in (mutation.samples or '').split(',')
            ]

        return [
            [mutation.cancer.code]
        ]

    def insert_details(self, mutations):
        for chunk in chunked_list(mutations.items()):
            db.session.bulk_insert_mappings(
                self.model,
                [
                    self.create_init_kwargs(mutation, data)
                    for mutation, data in chunk
                ]
            )
            db.session.flush()

    def update_details(self, mutations):
        """Unfortunately mutation_id does not maps 1-1 for CancerMutation, so
        additional field for filter is required - hence use of cancer_id and
        hence cancer_id will not be updated with this method."""
        for mutation, data in mutations.items():
            kwargs = self.create_init_kwargs(mutation, data)
            try:
                mut = self.model.query.filter_by(
                    mutation_id=mutation[0],
                    cancer_id=mutation[1]
                ).one()
            except NoResultFound:
                mut = self.model(**kwargs)
                db.session.add(mut)

            for key, value in kwargs.items():
                setattr(mut, key, value)
