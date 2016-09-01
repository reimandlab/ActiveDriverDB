from database import db
from database import get_or_create
from models import Cancer
from models import CancerMutation
from import_mutations import MutationImporter
from helpers.parsers import parse_tsv_file
from helpers.parsers import chunked_list


class Importer(MutationImporter):

    model = CancerMutation
    default_path = 'data/mutations/TCGA_muts_annotated.txt'

    def parse(self, path):
        from collections import Counter
        mutations_counter = Counter()

        def cancer_parser(line):

            assert line[10].startswith('comments: ')
            cancer_name, sample, _ = line[10][10:].split(';')

            cancer, created = get_or_create(Cancer, name=cancer_name)

            if created:
                db.session.add(cancer)

            for mutation_id in self.preparse_mutations(line):

                mutations_counter[
                    (
                        mutation_id,
                        cancer.id,
                    )
                ] += 1

        parse_tsv_file(path, cancer_parser)
        return mutations_counter

    def insert_details(self, mutations_counter):
        for chunk in chunked_list(mutations_counter.items()):
            db.session.bulk_insert_mappings(
                self.model,
                [
                    {
                        'mutation_id': mutation[0],
                        'cancer_id': mutation[1],
                        'count': count
                    }
                    for mutation, count in chunk
                ]
            )
            db.session.flush()