from collections import defaultdict

from sqlalchemy.orm.exc import NoResultFound

from database import db
from database import get_or_create
from models import Cancer
from models import TCGAMutation
from helpers.parsers import iterate_tsv_gz_file
from helpers.parsers import chunked_list

from .mutation_importer import MutationImporter


class TCGAImporter(MutationImporter):

    name = 'tcga'
    model = TCGAMutation
    default_path = 'data/mutations/TCGA_muts_annotated.txt.gz'
    header = [
        'Chr', 'Start', 'End', 'Ref', 'Alt', 'Func.refGene', 'Gene.refGene',
        'GeneDetail.refGene', 'ExonicFunc.refGene', 'AAChange.refGene', 'V11'
    ]
    samples_to_skip = set()

    def __init__(self, *args, export_samples=False, **kwargs):
        super().__init__(*args, **kwargs)

        self.export_samples = None
        self.export_details = None
        self.rebind_exporter(export_samples)

    def export(self, *args, export_samples=None, **kwargs):
        if export_samples is not None:
            self.rebind_exporter(export_samples)

        super().export(*args, **kwargs)

    def rebind_exporter(self, export_samples):
        self.export_details = (
            self.export_details_with_samples
            if export_samples else
            self.export_details_without_samples
        )
        self.export_samples = export_samples

    def decode_line(self, line):
        assert line[10].startswith('comments: ')
        cancer_name, sample_name, _ = line[10][10:].split(';')
        return cancer_name, sample_name

    def iterate_lines(self, path):
        return iterate_tsv_gz_file(path, file_header=self.header)

    def parse(self, path):

        mutations = defaultdict(lambda: [0, set()])

        for line in self.iterate_lines(path):
            cancer_name, sample_name = self.decode_line(line)

            if sample_name in self.samples_to_skip:
                continue

            cancer, created = get_or_create(Cancer, name=cancer_name)

            if created:
                # set code (temporarily) to the cancer name
                cancer.code = cancer_name
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
        return ['cancer_type', 'count']

    def export_details(self, mutation):
        raise NotImplementedError

    @staticmethod
    def export_details_without_samples(mutation):
        return [(mutation.cancer.code, str(mutation.count))]

    @staticmethod
    def export_details_with_samples(mutation):
        return [
            (mutation.cancer.code, sample)
            for sample in (mutation.samples or '').split(',')
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
