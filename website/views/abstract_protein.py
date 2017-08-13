import flask
from flask import request, flash
from flask_classful import FlaskView
from flask_login import current_user
from sqlalchemy import and_

from helpers.filters import FilterManager
from models import Protein, Mutation, UsersMutationsDataset


class GracefulFilterManager(FilterManager):

    def update_from_request_gracefully(self, request):
        # sometimes user comes with a disease which is not associated
        # with any of mutations in given protein. We do not want to
        # raise ValidationError for the user, but rather just skip
        # the faulty filter value and let the user know of that.

        # Example:
        # /protein/show/NM_001042351?filters=Mutation.disease_name:in:%27Cataract,%20nuclear%20total%27,G6PD%20SPLIT;Mutation.sources:in:ClinVar
        skipped_filters, rejected_values_by_filters = self.update_from_request(request, raise_on_forbidden=False)

        for filter_id, rejected_values in rejected_values_by_filters.items():
            filtered_property = filter_id.split('.')[-1].replace('_', ' ')

            plural = len(rejected_values) > 1

            message = (
                '<i>%s</i> %s not occur in <i>%s</i> for this protein '
                'and therefore %s left out.'
                %
                (
                    ', '.join(rejected_values),
                    'do' if plural else 'does',
                    filtered_property,
                    'they were' if plural else 'it was'
                )
            )

            flash(message, category='warning')


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

        flask.g.filter_manager = filter_manager

        endpoint = self.build_route_name(name)

        return filter_manager.reformat_request_url(
            request, endpoint, *args, **kwargs
        )

    @property
    def filter_manager(self):
        return flask.g.filter_manager

    def get_protein_and_manager(self, refseq, **kwargs):
        protein = Protein.query.filter_by(refseq=refseq).first_or_404()
        return protein, self.filter_manager


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
