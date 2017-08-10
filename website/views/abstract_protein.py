from flask import request
from flask_classful import FlaskView
from flask_login import current_user
from sqlalchemy import and_

from models import Protein, Mutation, UsersMutationsDataset


class AbstractProteinView(FlaskView):

    filter_class = None

    def before_request(self, name, *args, **kwargs):

        user_datasets = current_user.datasets_names_by_uri()
        refseq = kwargs.get('refseq', None)
        protein = (
            Protein.query.filter_by(refseq=refseq).first_or_404()
            if refseq else
            None
        )

        filter_manager = self.filter_class(
            protein,
            custom_datasets_ids=user_datasets.keys()
        )
        endpoint = self.build_route_name(name)

        return filter_manager.reformat_request_url(
            request, endpoint, *args, **kwargs
        )

    def get_protein_and_manager(self, refseq, **kwargs):
        protein = Protein.query.filter_by(refseq=refseq).first_or_404()
        user_datasets = current_user.datasets_names_by_uri()
        filter_manager = self.filter_class(
            protein,
            custom_datasets_ids=user_datasets.keys(),
            **kwargs
        )
        return protein, filter_manager


def get_raw_mutations(protein, filter_manager, count=False):

    custom_dataset = filter_manager.get_value('UserMutations.sources')

    mutation_filters = [Mutation.protein == protein]

    if custom_dataset:
        dataset = UsersMutationsDataset.query.filter_by(
            uri=custom_dataset
        ).one()

        filter_manager.filters['Mutation.sources']._value = 'user'

        mutation_filters.append(
            Mutation.id.in_([m.id for m in dataset.mutations])
        )

    getter = filter_manager.query_count if count else filter_manager.query_all

    raw_mutations = getter(
        Mutation,
        lambda q: and_(q, and_(*mutation_filters))
    )

    return raw_mutations
