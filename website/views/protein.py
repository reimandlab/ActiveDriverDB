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
from website.helpers.filters import FilterSet
from website.helpers.filters import Filters
from website.helpers.filters import Filter


class ProteinView(FlaskView):
    """Single protein view: includes needleplot and sequence"""

    allowed_filters = FilterSet([
        Filter('sources', 'in', 'TCGA', 'select', 'Source',
               choices=list(Mutation.source_fields.keys())),
        Filter('is_ptm', 'eq', None, 'with_without', 'PTM mutations'),
    ])

    def index(self):
        """Show SearchView as deafault page"""
        return redirect(url_for('SearchView:index', target='proteins'))

    def show(self, refseq):
        """Show a protein by:

        + needleplot
        + tracks (seuqence + data tracks)
        """
        active_filters = FilterSet.from_request(request)

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()

        disorder = [
            TrackElement(*region) for region in protein.disorder_regions
        ]
        mutations = active_filters.filtered(protein.mutations)

        tracks = [
            PositionTrack(protein.length, 25),
            SequenceTrack(protein),
            Track('disorder', disorder),
            Track(
                'domains',
                [
                    TrackElement(
                        domain.start,
                        domain.end - domain.start,
                        domain.interpro.accession,
                        domain.interpro.description
                    )
                    for domain in protein.domains
                ]
            ),
            MutationsTrack(mutations)
        ]

        filters = Filters(active_filters, self.allowed_filters)

        # repeated on purpose
        mutations = active_filters.filtered(protein.mutations)

        return template('protein.html', protein=protein, tracks=tracks,
                        filters=filters, mutations=mutations)

    def mutations(self, refseq):
        """List of mutations suitable for needleplot library"""
        protein = Protein.query.filter_by(refseq=refseq).first_or_404()
        filters = request.args.get('filters', '')
        filters = FilterSet.from_string(filters)

        response = []

        source = filters.sources
        source_field_name = Mutation.source_fields[source]

        mutations = list(filter(filters.test, protein.mutations))

        for mutation in mutations:

            needle = {
                'coord': mutation.position,
                'value': getattr(mutation, source_field_name).value,
                'category': mutation.impact_on_ptm
            }
            response += [needle]

        return jsonify(response)

    def sites(self, refseq):
        """List of sites suitable for needleplot library"""

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()

        response = [
            {
                'start': str(site.position - 7),
                'end': str(site.position + 7),
                'type': str(site.type)
            } for site in protein.sites
        ]

        return jsonify(response)
