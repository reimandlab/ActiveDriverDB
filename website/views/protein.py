from flask import request
from flask import jsonify
from flask import redirect
from flask import url_for
from flask import render_template as template
from flask_classful import FlaskView
from flask_classful import route
from flask_login import current_user
from models import Protein
from models import Mutation
from models import Domain
from models import Site
from models import UsersMutationsDataset
from helpers.tracks import Track
from helpers.tracks import TrackElement
from helpers.tracks import PositionTrack
from helpers.tracks import SequenceTrack
from helpers.tracks import MutationsTrack
from helpers.tracks import DomainsTrack
from helpers.filters import FilterManager
from helpers.views import AjaxTableView
from ._global_filters import common_filters, create_dataset_specific_widgets, filters_data_view
from ._global_filters import create_widgets
from ._commons import represent_mutation
from operator import attrgetter
from sqlalchemy import and_


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


def get_raw_mutations(protein, filter_manager, source):

    custom_dataset = filter_manager.get_value('UserMutations.sources')

    mutation_filters = [Mutation.protein == protein]

    if custom_dataset:
        source = 'user'

    if source == 'user':
        dataset = UsersMutationsDataset.query.filter_by(
            uri=custom_dataset
        ).one()

        filter_manager.filters['Mutation.sources']._value = 'user'

        mutation_filters.append(
            Mutation.id.in_([m.id for m in dataset.mutations])
        )

    raw_mutations = filter_manager.query_all(
        Mutation,
        lambda q: and_(q, and_(*mutation_filters))
    )

    return raw_mutations


def prepare_representation_data(protein, filter_manager):
    source = filter_manager.get_value('Mutation.sources')

    raw_mutations = get_raw_mutations(protein, filter_manager, source)

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


class ProteinViewFilters(FilterManager):

    def __init__(self, protein, **kwargs):
        filters = common_filters(protein, **kwargs)
        super().__init__(filters)
        self.update_from_request(request)


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


class ProteinView(FlaskView):
    """Single protein view: includes needleplot and sequence"""

    def before_request(self, name, *args, **kwargs):
        user_datasets = current_user.datasets_names_by_uri()
        refseq = kwargs.get('refseq', None)
        protein = Protein.query.filter_by(refseq=refseq).first_or_404() if refseq else None

        filter_manager = ProteinViewFilters(
            protein,
            custom_datasets_ids=user_datasets.keys()
        )
        endpoint = self.build_route_name(name)

        return filter_manager.reformat_request_url(
            request, endpoint, *args, **kwargs
        )

    def index(self):
        """Show SearchView as default page"""
        return redirect(url_for('SearchView:default', target='proteins'))

    def browse(self):
        return template('protein/browse.html')

    browse_data = route('browse_data')(
        AjaxTableView.from_model(
            Protein,
            search_filter=(
                lambda q: Protein
                .gene_name.remote_attr
                .like(q + '%')
            ),
            sort='gene_name'
        )
    )

    def details(self, refseq):
        protein = Protein.query.filter_by(refseq=refseq).first_or_404()

        filter_manager = ProteinViewFilters(protein)

        source = filter_manager.get_value('Mutation.sources')

        source_column = Mutation.source_fields[source]

        json = protein.to_json(data_filter=filter_manager.apply)

        meta = set()

        if source in ('1KGenomes', 'ESP6500'):
            summary_getter = attrgetter('affected_populations')
        else:
            def summary_getter(meta_column):
                return meta_column.summary()

        for mutation in filter_manager.apply(protein.mutations):
            meta_column = getattr(mutation, source_column)
            if not meta_column:
                continue
            meta.update(
                summary_getter(meta_column)
            )

        json['meta'] = list(meta)

        return jsonify(json)

    def representation_data(self, refseq):

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()
        user_datasets = current_user.datasets_names_by_uri()
        filter_manager = ProteinViewFilters(
            protein,
            custom_datasets_ids=user_datasets.keys()
        )

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
            'filters': filters_data_view(filter_manager)
        }

        return jsonify(response)

    def show(self, refseq):
        """Show a protein by:

        + needleplot
        + tracks (sequence + data tracks)
        """

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()
        user_datasets = current_user.datasets_names_by_uri()
        filter_manager = ProteinViewFilters(
            protein,
            custom_datasets_ids=user_datasets.keys()
        )

        # data = prepare_representation_data(protein, filter_manager)

        return template(
            'protein/show.html',
            protein=protein,
            filters=filter_manager,
            widgets=create_widgets(
                filter_manager.filters,
                custom_datasets_names=user_datasets.values()
            ),
            site_types=['multi_ptm'] + Site.types,
            mutation_types=Mutation.types,
            # **data
        )

    def mutation(self, refseq, position, alt):
        from .chromosome import represent_mutations
        from database import get_or_create

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()

        filter_manager = ProteinViewFilters(
            protein,
            default_source=None,
            source_nullable=False
        )

        mutation, _ = get_or_create(
            Mutation,
            protein=protein,
            # setting id directly is easier than forcing update outside session
            protein_id=protein.id,
            position=int(position),
            alt=alt
        )

        raw_mutations = filter_manager.apply([mutation])

        assert len(raw_mutations) == 1

        if not raw_mutations:
            return jsonify(
                'There is a mutation, but it does not satisfy given filters'
            )

        parsed_mutations = represent_mutations(
            raw_mutations, filter_manager
        )

        return jsonify(parsed_mutations)

    def known_mutations(self, refseq, filter_manager=None):
        """List of mutations suitable for needleplot library"""

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()

        if not filter_manager:
            filter_manager = ProteinViewFilters(protein)

        raw_mutations = filter_manager.query_all(
            Mutation,
            lambda q: and_(q, Mutation.protein_id == protein.id)
        )

        parsed_mutations = represent_needles(
            raw_mutations,
            filter_manager
        )

        return jsonify(parsed_mutations)

    def sites(self, refseq, filter_manager=None):
        """List of sites suitable for needleplot library"""

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()

        if not filter_manager:
            filter_manager = ProteinViewFilters(protein)

        response = prepare_sites(protein, filter_manager)

        return jsonify(response)
