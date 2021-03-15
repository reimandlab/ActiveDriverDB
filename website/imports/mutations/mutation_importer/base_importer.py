from database import db
from database.bulk import get_highest_id
from helpers.parsers import chunked_list
from models import Mutation


class BaseMutationsImporter:
    """Imports 'cores of mutations' - data used to build 'Mutation' instances
    so columns common for different metadata like: 'position', 'alt' etc."""

    def prepare(self):
        # reset base_mutations
        self.mutations = {}

        # for bulk_inserts it's needed to generate identifiers manually so
        # here the highest id currently in use in the database is retrieved.
        self.highest_base_id = self.get_highest_id()

    def get_highest_id(self):
        return get_highest_id(Mutation)

    def get_or_make_mutation(self, pos, protein_id, alt, is_ptm):

        key = (pos, protein_id, alt)
        if key in self.mutations:
            return self.mutations[key][0]
        else:

            mutation_id = db.session.query(Mutation.id).filter_by(
                position=pos, protein_id=protein_id, alt=alt
            ).scalar()

            if mutation_id is None:
                self.highest_base_id += 1
                mutation_id = self.highest_base_id
                self.mutations[key] = (mutation_id, is_ptm)

            return mutation_id

    def insert(self):
        for chunk in chunked_list(self.mutations.items()):
            db.session.bulk_insert_mappings(
                Mutation,
                [
                    {
                        'id': data[0],
                        'precomputed_is_ptm': data[1],
                        'position': mutation[0],
                        'protein_id': mutation[1],
                        'alt': mutation[2]
                    }
                    for mutation, data in chunk
                ]
            )
            db.session.flush()
