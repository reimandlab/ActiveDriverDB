from operator import attrgetter

from flask import jsonify
from flask import redirect
from flask import render_template as template
from flask import request
from flask import url_for
from flask_login import current_user
from sqlalchemy import and_
from stats import stats
from helpers.tracks import DomainsTrack
from helpers.tracks import MutationsTrack
from helpers.tracks import SequenceTrack
from helpers.tracks import Track
from helpers.tracks import TrackElement
from models import Domain, PopulationMutation
from models import Mutation
from models import Site
from views.abstract_protein import AbstractProteinView, GracefulFilterManager, ProteinRepresentation, get_raw_mutations
from ._commons import represent_mutation
from .filters import common_filters, ProteinFiltersData, SourceDependentFilter, cached_queries
from .filters import create_widgets


def prepare_tracks(protein, raw_mutations):

    disorder = [
        TrackElement(*region) for region in protein.disorder_regions
    ]
    tracks = [
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


def prepare_sites(sites):
    return [
        {
            'start': site.position - 7,
            'end': site.position + 7,
            'type': str(site.type)
        } for site in sites
    ]


mc3_exomes_cnt = stats.mc3_exomes()


class SequenceRepresentation(ProteinRepresentation):

    def __init__(self, protein, filter_manager, include_kinases_from_groups=False):
        super().__init__(protein, filter_manager, include_kinases_from_groups)

        background_sources = filter_manager.get_value('Background.sources')

        if background_sources:
            self.background_mutations = {}
            chosen_source_name = filter_manager.get_value('Mutation.sources')

            for background_source in background_sources:
                filter_manager.set_value('Mutation.sources', background_source)
                self.background_mutations[background_source] = get_raw_mutations(protein, filter_manager)

            # restore real source
            filter_manager.set_value('Mutation.sources', chosen_source_name)

        sites, kinases, kinase_groups = self.get_sites_and_kinases(only_sites_with_kinases=False)

        tracks = prepare_tracks(protein, self.protein_mutations)

        source = filter_manager.get_value('Mutation.sources')
        source_model = Mutation.get_source_model(source)
        value_type = source_model.value_type

        parsed_mutations, background_mutations = self.represent_needles()
        background = filter_manager.get_value('Background.sources')

        self.json_data = {
            'value_type': value_type if not background else 'frequency',
            'log_scale': (value_type == 'frequency') or bool(background),
            'mutations': parsed_mutations,
            'background_mutations': background_mutations,
            'sites': prepare_sites(sites),
            'tracks': tracks
        }

    def create_needles(self, mutations, source, get_value, background=False):
        get_source_data = attrgetter(Mutation.source_fields[source])
        data_filter = self.filter_manager.apply
        get_mimp_data = attrgetter('meta_MIMP')

        needles = []

        for mutation in mutations:

            field = get_source_data(mutation)
            needle = represent_mutation(mutation, data_filter)

            metadata = {source: field.to_json(data_filter)}

            mimp = get_mimp_data(mutation)

            if mimp:
                metadata['MIMP'] = mimp.to_json()

            if background:
                needle['background'] = True

            needle['meta'] = metadata
            needle['value'] = get_value(field)
            needle['category'] = mutation.impact_on_ptm(data_filter)

            needles.append(needle)

        return needles

    def represent_needles(self):

        source_name = self.filter_manager.get_value('Mutation.sources')

        background = []
        background_sources = self.filter_manager.get_value('Background.sources')

        data_filter = self.filter_manager.apply

        def get_value(field):
            return field.get_value(data_filter)

        if background_sources:
            for background_source in background_sources:
                self.filter_manager.set_value('Mutation.sources', background_source)

                background.extend(
                    self.create_needles(
                        self.background_mutations[background_source],
                        background_source,
                        get_value,
                        background=True
                    )
                )

            self.filter_manager.set_value('Mutation.sources', source_name)

            # only MC3 can be easily rescaled to frequency
            assert source_name == 'MC3'

            def get_value(field):
                return field.get_value(data_filter) / mc3_exomes_cnt

        needles = self.create_needles(self.protein_mutations, source_name, get_value)

        return needles, background


class Background:
    pass


def background_widget(filters_by_id):
    from helpers.widgets import FilterWidget

    return FilterWidget(
        'Background', 'checkbox_multiple',
        filter=filters_by_id['Background.sources'],
        labels=cached_queries.dataset_labels,
        all_selected_label='All population datasets'
    )


def background_filter():

    return SourceDependentFilter(
        Background, 'sources',
        comparators=['in'],
        choices=[
            name
            for name in Mutation.sources_dict.keys()
            if issubclass(Mutation.get_source_model(name), PopulationMutation)
        ],
        default=[],
        nullable=True,
        source='MC3',
        multiple='any'
    )


class SequenceViewFilters(GracefulFilterManager):

    def __init__(self, protein, **kwargs):

        filters = common_filters(protein, **kwargs) + [background_filter()]
        super().__init__(filters)
        self.update_from_request(request)


class SequenceView(AbstractProteinView):
    """Single protein view: includes needleplot and sequence"""

    filter_class = SequenceViewFilters

    def index(self):
        """Show SearchView as default page"""
        return redirect(url_for('SearchView:default', target='proteins'))

    def representation_data(self, refseq):

        protein, filter_manager = self.get_protein_and_manager(refseq)

        data = SequenceRepresentation(protein, filter_manager).as_json()

        mutations = data['mutations']
        background_mutations = data.pop('background_mutations')

        data['mutation_table'] = template(
            'protein/mutation_table.html',
            mutations=filter_manager.apply(mutations),
            filters=filter_manager,
            protein=protein,
            value_type=data['value_type']
        )
        data['tracks'] = template(
            'protein/tracks.html',
            tracks=data['tracks']
        )
        data['mutations'].extend(background_mutations)

        response = {
            'content': data,
            'filters': ProteinFiltersData(
                filter_manager,
                protein,
                lambda _, filters: [background_widget(filters)]
            ).to_json()
        }

        return jsonify(response)

    def show(self, refseq):
        """Show a protein by:

        + needleplot
        + tracks (sequence + data tracks)
        """

        protein, filter_manager = self.get_protein_and_manager(refseq)

        user_datasets = current_user.datasets_names_by_uri()

        widgets = create_widgets(
            protein,
            filter_manager.filters,
            custom_datasets_names=user_datasets.values()
        )
        widgets['dataset_specific'].append(background_widget(filter_manager.filters))

        return template(
            'protein/show.html',
            protein=protein,
            filters=filter_manager,
            widgets=widgets,
            site_types=['multi_ptm'] + Site.types,
            mutation_types=Mutation.types,
        )
