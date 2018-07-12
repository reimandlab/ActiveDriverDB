from models import Protein, Mutation


class SearchResult:

    def __init__(self, protein, mutation, is_mutation_novel, type, **kwargs):
        self.protein = protein
        self.mutation = mutation
        self.is_mutation_novel = is_mutation_novel
        self.type = type
        self.meta_user = None
        self.__dict__.update(kwargs)

    def __getstate__(self):
        state = self.__dict__.copy()

        state['protein_refseq'] = self.protein.refseq
        del state['protein']

        state['mutation_kwargs'] = {
            'position': self.mutation.position,
            'alt': self.mutation.alt
        }
        del state['mutation']

        state['meta_user'].mutation = None

        return state

    def __setstate__(self, state):

        state['protein'] = Protein.query.filter_by(
            refseq=state['protein_refseq']
        ).one()
        del state['protein_refseq']

        state['mutation'] = Mutation.query.filter_by(
            protein=state['protein'],
            **state['mutation_kwargs']
        ).one()
        del state['mutation_kwargs']

        state['meta_user'].mutation = state['mutation']
        state['mutation'].meta_user = state['meta_user']

        self.__dict__.update(state)
