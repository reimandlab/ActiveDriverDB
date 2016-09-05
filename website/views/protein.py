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


def get_source_field(filters):
    source = filters.sources
    source_field_name = Mutation.source_fields[source]
    return source_field_name


def get_response_content(response):
    return response.get_data().decode('ascii')


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
        raw_mutations = active_filters.filtered(protein.mutations)

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
            MutationsTrack(raw_mutations)
        ]

        filters = Filters(active_filters, self.allowed_filters)

        if filters.active.sources in ('TCGA', 'ClinVar'):
            value_type = 'Count'
        else:
            value_type = 'Frequency'

        # repeated on purpose
        raw_mutations = active_filters.filtered(protein.mutations)

        parsed_mutations = self._represent_mutations(
            raw_mutations,
            active_filters.sources,
            get_source_field(active_filters)
        )

        return template(
            'protein.html', protein=protein, tracks=tracks,
            filters=filters, value_type=value_type,
            log_scale=(value_type == 'Frequency'),
            mutations=parsed_mutations,
            sites=get_response_content(self.sites(refseq)),
        )

    def mutations(self, refseq):
        """List of mutations suitable for needleplot library"""

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()
        active_filters = FilterSet.from_request(request)

        raw_mutations = active_filters.filtered(protein.mutations)

        parsed_mutations = self._represent_mutations(
            raw_mutations,
            active_filters.sources,
            get_source_field(active_filters)
        )

        return jsonify(parsed_mutations)

    def sites(self, refseq):
        """List of sites suitable for needleplot library"""

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()

        response = [
            {
                'start': site.position - 7,
                'end': site.position + 7,
                'type': str(site.type)
            } for site in protein.sites
        ]

        return jsonify(response)

    @staticmethod
    def _represent_mutations(mutations, source, source_field_name):

        response = []

        def get_metadata(mutation):
            nonlocal source_field_name, source
            meta = {}
            source_specific_data = getattr(mutation, source_field_name)
            if isinstance(source_specific_data, list):
                meta[source] = {
                    source + ' metadata':
                    [
                        datum.representation
                        for datum in source_specific_data
                    ]
                }
                meta[source][source + ' metadata'].sort(
                    key=lambda rep: rep['Value'],
                    reverse=True
                )
            else:
                meta[source] = source_specific_data.representation
            mimp = getattr(mutation, 'meta_MIMP')
            if mimp:
                meta['MIMP'] = mimp.representation
            return meta

        def get_value(mutation):
            nonlocal source_field_name

            meta = getattr(mutation, source_field_name)
            if isinstance(meta, list):
                return sum((data.value for data in meta))
            return meta.value

        for mutation in mutations:
            needle = {
                'coord': mutation.position,
                'value': get_value(mutation),
                'category': mutation.impact_on_ptm,
                'alt': mutation.alt,
                'ref': mutation.ref,
                'meta': get_metadata(mutation),
                'sites': [
                    site.representation
                    for site in mutation.find_closest_sites()
                ]
            }
            response += [needle]

        return response
