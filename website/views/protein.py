from flask import request
from flask import jsonify
from flask import redirect
from flask import url_for
from flask import render_template as template
from flask_classful import FlaskView
from models import Protein
from models import Mutation
from website.helpers.tracks import Track
from website.helpers.tracks import TrackElement
from website.helpers.tracks import PositionTrack
from website.helpers.tracks import SequenceTrack
from website.helpers.tracks import MutationsTrack
from website.helpers.tracks import DomainsTrack
from website.helpers.filters import FilterManager
from website.views._global_filters import common_filters
from website.views._global_filters import common_widgets
from website.views._commons import represent_mutations


class ProteinView(FlaskView):
    """Single protein view: includes needleplot and sequence"""

    def _make_filters(self):
        filters = common_filters()
        filter_manager = FilterManager(filters)
        return filters, filter_manager

    def _make_widgets(self, filters):
        return common_widgets(filters)

    def index(self):
        """Show SearchView as deafault page"""
        return redirect(url_for('SearchView:index', target='proteins'))

    def show(self, refseq):
        """Show a protein by:

        + needleplot
        + tracks (seuqence + data tracks)
        """
        filters, filter_manager = self._make_filters()
        filter_widgets = self._make_widgets(filters)
        filter_manager.update_from_request(request)

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()

        disorder = [
            TrackElement(*region) for region in protein.disorder_regions
        ]

        raw_mutations = filter_manager.apply(protein.mutations)

        tracks = [
            PositionTrack(protein.length, 25),
            SequenceTrack(protein),
            Track('disorder', disorder),
            DomainsTrack(protein.domains),
            MutationsTrack(raw_mutations)
        ]

        source = filter_manager.get_value('Mutation.sources')
        if source in ('TCGA', 'ClinVar'):
            value_type = 'Count'
        else:
            value_type = 'Frequency'

        parsed_mutations = represent_mutations(
            raw_mutations, filter_manager
        )

        return template(
            'protein/index.html', protein=protein, tracks=tracks,
            filters=filter_manager,
            filter_widgets=filter_widgets,
            value_type=value_type,
            log_scale=(value_type == 'Frequency'),
            mutations=parsed_mutations,
            sites=self._prepare_sites(protein, filter_manager),
        )

    def known_mutation(self, refseq, position, alt):
        _, filter_manager = self._make_filters()

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()

        mutation = Mutation.query.filter_by(
            protein=protein, position=position, alt=alt
        ).first_or_404()

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
            _, filter_manager = self._make_filters()

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()

        raw_mutations = filter_manager.apply(protein.mutations)

        parsed_mutations = represent_mutations(
            raw_mutations,
            filter_manager
        )

        return jsonify(parsed_mutations)

    def sites(self, refseq, filter_manager=None):
        """List of sites suitable for needleplot library"""

        if not filter_manager:
            _, filter_manager = self._make_filters()

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()

        response = self._prepare_sites(protein)

        return jsonify(response)

    def _prepare_sites(self, protein, filter_manager):
        sites = filter_manager.apply(protein.sites)
        return [
            {
                'start': site.position - 7,
                'end': site.position + 7,
                'type': str(site.type)
            } for site in sites
        ]
