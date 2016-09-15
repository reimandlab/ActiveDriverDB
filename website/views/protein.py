from flask import request
from flask import jsonify
from flask import redirect
from flask import url_for
from flask import render_template as template
from flask_classful import FlaskView
from models import Cancer
from models import Protein
from models import Mutation
from models import Site
from models import The1000GenomesMutation
from models import ExomeSequencingMutation
from website.helpers.tracks import Track
from website.helpers.tracks import TrackElement
from website.helpers.tracks import PositionTrack
from website.helpers.tracks import SequenceTrack
from website.helpers.tracks import MutationsTrack
from website.helpers.filters import Filter
from website.helpers.filters import FilterManager


def get_source_field(source):
    source_field_name = Mutation.source_fields[source]
    return source_field_name


def get_response_content(response):
    return response.get_data().decode('ascii')


class SourceDependentFilter(Filter):

    def __init__(self, *args, **kwargs):
        self.source = kwargs.pop('source')
        super().__init__(*args, **kwargs)

    @property
    def visible(self):
        return self.manager.get_value('Mutation.sources') == self.source


class ProteinView(FlaskView):
    """Single protein view: includes needleplot and sequence"""

    cancer_types = [cancer.name for cancer in Cancer.query.all()]
    populations_1kg = The1000GenomesMutation.populations.values()
    populations_esp = ExomeSequencingMutation.populations.values()

    filter_manager = FilterManager(
        [
            Filter(
                'Source', Mutation, 'sources', widget='select',
                comparators=['in'], default_comparator='in',
                choices=list(Mutation.source_fields.keys()),
                default='TCGA', nullable=False,
            ),
            Filter(
                'PTM mutations', Mutation, 'is_ptm', widget='with_without',
                comparators=['eq'], default_comparator='eq',
            ),
            Filter(
                'Site type', Site, 'type', widget='select',
                comparators=['in'], default_comparator='in',
                choices=['phosphorylation', 'acetylation', 'ubiquitination', 'methylation'],
            ),
            SourceDependentFilter(
                'Cancer', Mutation, 'cancer_types', widget='select_multiple',
                comparators=['in'], default_comparator='in',
                choices=cancer_types,
                default=cancer_types, nullable=False,
                source='TCGA',
                multiple='any',
            ),
            SourceDependentFilter(
                'Population', Mutation, 'populations_1KG', widget='select_multiple',
                comparators=['in'], default_comparator='in',
                choices=populations_1kg,
                default=populations_1kg, nullable=False,
                source='1KGenomes',
                multiple='any',
            ),
            SourceDependentFilter(
                'Population', Mutation, 'populations_ESP6500', widget='select_multiple',
                comparators=['in'], default_comparator='in',
                choices=populations_esp,
                default=populations_esp, nullable=False,
                source='ESP6500',
                multiple='any',
            )
        ]
    )

    def before_request(self, name, *args, **kwargs):
        self.filter_manager.reset()
        self.filter_manager.update_from_request(request)

    def index(self):
        """Show SearchView as deafault page"""
        return redirect(url_for('SearchView:index', target='proteins'))

    def show(self, refseq):
        """Show a protein by:

        + needleplot
        + tracks (seuqence + data tracks)
        """
        protein = Protein.query.filter_by(refseq=refseq).first_or_404()

        disorder = [
            TrackElement(*region) for region in protein.disorder_regions
        ]
        raw_mutations = self.filter_manager.apply(Mutation, protein.mutations)

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

        source = self.filter_manager.get_value('Mutation.sources')
        if source in ('TCGA', 'ClinVar'):
            value_type = 'Count'
        else:
            value_type = 'Frequency'

        parsed_mutations = self._represent_mutations(
            raw_mutations,
            source,
            get_source_field(source)
        )

        return template(
            'protein.html', protein=protein, tracks=tracks,
            filters=self.filter_manager, value_type=value_type,
            log_scale=(value_type == 'Frequency'),
            mutations=parsed_mutations,
            sites=self._prepare_sites(protein),
        )

    def mutations(self, refseq):
        """List of mutations suitable for needleplot library"""

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()

        raw_mutations = self.filter_manager.apply(Mutation, protein.mutations)

        parsed_mutations = self._represent_mutations(
            raw_mutations,
            source,
            get_source_field(source)
        )

        return jsonify(parsed_mutations)

    def sites(self, refseq):
        """List of sites suitable for needleplot library"""

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()

        response = self._prepare_sites(protein)

        return jsonify(response)

    def _prepare_sites(self, protein):
        sites = self.filter_manager.apply(Site, protein.sites)
        return [
            {
                'start': site.position - 7,
                'end': site.position + 7,
                'type': str(site.type)
            } for site in sites
        ]

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
                mimp_representation = mimp.representation
                mimp_representation['sites'] = [
                    site.representation for site in mutation.sites
                ]
                meta['MIMP'] = mimp_representation
            return meta

        def get_summary(mutation):
            source_specific_data = getattr(mutation, source_field_name)
            if isinstance(source_specific_data, list):
                return [
                    datum.summary
                    for datum in source_specific_data
                ]
            else:
                return source_specific_data.summary

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
                ],
                'cnt_ptm': mutation.cnt_ptm_affected,
                'summary': get_summary(mutation),
            }
            response += [needle]

        return response
