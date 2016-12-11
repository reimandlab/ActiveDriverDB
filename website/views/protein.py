from flask import request
from flask import jsonify
from flask import redirect
from flask import url_for
from flask import render_template as template
from flask_classful import FlaskView
from flask_classful import route
from models import Protein
from models import Mutation
from models import Domain
from models import Site
from website.helpers.tracks import Track
from website.helpers.tracks import TrackElement
from website.helpers.tracks import PositionTrack
from website.helpers.tracks import SequenceTrack
from website.helpers.tracks import MutationsTrack
from website.helpers.tracks import DomainsTrack
from website.helpers.filters import FilterManager
from website.helpers.views import AjaxTableView
from website.views._global_filters import common_filters
from website.views._global_filters import create_widgets
from website.views._commons import represent_mutation
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


class ProteinViewFilters(FilterManager):

    def __init__(self, **kwargs):
        filters = common_filters(**kwargs)
        super().__init__(filters)
        self.update_from_request(request)


class ProteinView(FlaskView):
    """Single protein view: includes needleplot and sequence"""

    def before_request(self, name, *args, **kwargs):
        filter_manager = ProteinViewFilters()
        endpoint = self.build_route_name(name)

        return filter_manager.reformat_request_url(
            request, endpoint, *args, **kwargs
        )

    def index(self):
        """Show SearchView as deafault page"""
        return redirect(url_for('SearchView:index', target='proteins'))

    def browse(self):
        return template('protein/browse.html')

    browse_data = route('browse_data')(
        AjaxTableView.from_model(
            Protein,
            search_filter=lambda q: Protein.gene_name.like(q + '%'),
            sort='gene_name'
        )
    )

    def show(self, refseq):
        """Show a protein by:

        + needleplot
        + tracks (seuqence + data tracks)
        """
        filter_manager = ProteinViewFilters()

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()

        disorder = [
            TrackElement(*region) for region in protein.disorder_regions
        ]

        source = filter_manager.get_value('Mutation.sources')

        raw_mutations = filter_manager.sqlalchemy_query(
            Mutation,
            lambda q: and_(q, Mutation.protein_id == protein.id)
        )

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

        if source in ('TCGA', 'ClinVar'):
            value_type = 'Count'
        else:
            value_type = 'Frequency'

        parsed_mutations = represent_needles(
            raw_mutations, filter_manager
        )

        filters_by_id = filter_manager.filters

        return template(
            'protein/index.html', protein=protein, tracks=tracks,
            filters=filter_manager,
            widgets=create_widgets(filters_by_id),
            value_type=value_type,
            log_scale=(value_type == 'Frequency'),
            mutations=parsed_mutations,
            sites=self._prepare_sites(protein, filter_manager),
        )

    def mutation(self, refseq, position, alt):
        from website.views.chromosome import represent_mutations
        from database import get_or_create

        filter_manager = ProteinViewFilters(
            default_source=None,
            source_nullable=False
        )

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()

        mutation, _ = get_or_create(
            Mutation,
            protein=protein,
            # setting id directly is easier than forcing update outside session
            protein_id=protein.id,
            position=int(position),
            alt=alt
        )

        raw_mutations = filter_manager.apply([mutation])

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

        if not filter_manager:
            filter_manager = ProteinViewFilters()

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()

        raw_mutations = filter_manager.sqlalchemy_query(
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

        if not filter_manager:
            filter_manager = ProteinViewFilters()

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()

        response = self._prepare_sites(protein)

        return jsonify(response)

    def _prepare_sites(self, protein, filter_manager):
        sites = filter_manager.sqlalchemy_query(
            Site,
            lambda q: and_(q, Site.protein_id == protein.id)
        )
        return [
            {
                'start': site.position - 7,
                'end': site.position + 7,
                'type': str(site.type)
            } for site in sites
        ]
