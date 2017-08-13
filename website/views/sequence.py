from operator import attrgetter

from flask import jsonify
from flask import redirect
from flask import render_template as template
from flask import request
from flask import url_for
from flask_login import current_user
from sqlalchemy import and_

from helpers.tracks import DomainsTrack
from helpers.tracks import MutationsTrack
from helpers.tracks import PositionTrack
from helpers.tracks import SequenceTrack
from helpers.tracks import Track
from helpers.tracks import TrackElement
from models import Domain
from models import Mutation
from models import Site
from views.abstract_protein import AbstractProteinView, get_raw_mutations, GracefulFilterManager
from ._commons import represent_mutation
from ._global_filters import common_filters, filters_data_view
from ._global_filters import create_widgets


def represent_needles(mutations, filter_manager):

    source_name = filter_manager.get_value('Mutation.sources')

    get_source_data = attrgetter(Mutation.source_fields[source_name])

    get_mimp_data = attrgetter('meta_MIMP')

    data_filter = filter_manager.apply

    response = []

    for mutation in mutations:

        needle = represent_mutation(mutation, data_filter)

        field = get_source_data(mutation)
        metadata = {
            source_name: field.to_json(data_filter)
        }

        mimp = get_mimp_data(mutation)

        if mimp:
            metadata['MIMP'] = mimp.to_json()

        needle['summary'] = field.summary(data_filter)
        needle['value'] = field.get_value(data_filter)
        needle['meta'] = metadata
        needle['category'] = mutation.impact_on_ptm(data_filter)

        response.append(needle)

    return response


def prepare_tracks(protein, raw_mutations):

    disorder = [
        TrackElement(*region) for region in protein.disorder_regions
    ]
    tracks = [
        PositionTrack(protein.length, 25),
        SequenceTrack(protein),
        Track('disorder', disorder),
        DomainsTrack(
            Domain.query.filter(
                and_(
                    Domain.protein == protein,
                    Domain.interpro.has(type='Domain')
                )
            )
        ),
        MutationsTrack(raw_mutations)
    ]
    return tracks


def prepare_representation_data(protein, filter_manager):
    source = filter_manager.get_value('Mutation.sources')

    raw_mutations = get_raw_mutations(protein, filter_manager)

    tracks = prepare_tracks(protein, raw_mutations)

    source_model = Mutation.get_source_model(source)
    value_type = source_model.value_type

    parsed_mutations = represent_needles(
        raw_mutations, filter_manager
    )

    needle_params = {
        'value_type': value_type,
        'log_scale': (value_type == 'frequency'),
        'mutations': parsed_mutations,
        'sites': prepare_sites(protein, filter_manager),
        'tracks': tracks
    }

    return needle_params


class SequenceViewFilters(GracefulFilterManager):

    def __init__(self, protein, **kwargs):

        filters = common_filters(protein, **kwargs)
        super().__init__(filters)
        self.update_from_request_gracefully(request)


def prepare_sites(protein, filter_manager):
    sites = filter_manager.query_all(
        Site,
        lambda q: and_(q, Site.protein == protein)
    )
    return [
        {
            'start': site.position - 7,
            'end': site.position + 7,
            'type': str(site.type)
        } for site in sites
    ]


class SequenceView(AbstractProteinView):
    """Single protein view: includes needleplot and sequence"""

    filter_class = SequenceViewFilters

    def index(self):
        """Show SearchView as default page"""
        return redirect(url_for('SearchView:default', target='proteins'))

    def representation_data(self, refseq):

        protein, filter_manager = self.get_protein_and_manager(refseq)

        data = prepare_representation_data(protein, filter_manager)

        data['mutation_table'] = template(
            'protein/mutation_table.html',
            mutations=data['mutations'],
            filters=filter_manager,
            protein=protein,
            value_type=data['value_type']
        )
        data['tracks'] = template(
            'protein/tracks.html',
            tracks=data['tracks']
        )

        response = {
            'representation': data,
            'filters': filters_data_view(protein, filter_manager)
        }

        return jsonify(response)

    def show(self, refseq):
        """Show a protein by:

        + needleplot
        + tracks (sequence + data tracks)
        """

        protein, filter_manager = self.get_protein_and_manager(refseq)

        user_datasets = current_user.datasets_names_by_uri()

        # data = prepare_representation_data(protein, filter_manager)

        return template(
            'protein/show.html',
            protein=protein,
            filters=filter_manager,
            widgets=create_widgets(
                protein,
                filter_manager.filters,
                custom_datasets_names=user_datasets.values()
            ),
            site_types=['multi_ptm'] + Site.types,
            mutation_types=Mutation.types,
            # **data
        )
