from flask import request
from flask import jsonify
from flask import redirect
from flask import url_for
from flask import render_template as template
from flask_classful import FlaskView
from models import Cancer
from models import Protein
from models import Mutation
from models import CancerMutation
from models import Site
from models import The1000GenomesMutation
from models import ExomeSequencingMutation
from models import ClinicalData
from website.helpers.tracks import Track
from website.helpers.tracks import TrackElement
from website.helpers.tracks import PositionTrack
from website.helpers.tracks import SequenceTrack
from website.helpers.tracks import MutationsTrack
from website.helpers.filters import Filter
from website.helpers.filters import FilterManager
from website.helpers.widgets import FilterWidget


def get_source_field(source):
    source_field_name = Mutation.source_fields[source]
    return source_field_name


def get_response_content(response):
    return response.get_data().decode('ascii')


def populations_labels(populations):
    return [
        population_name + ' (' + field_name[4:].upper() + ')'
        for field_name, population_name
        in populations.items()
    ]


class SourceDependentFilter(Filter):

    def __init__(self, *args, **kwargs):
        self.source = kwargs.pop('source')
        super().__init__(*args, **kwargs)

    @property
    def visible(self):
        return self.manager.get_value('Mutation.sources') == self.source


class ProteinView(FlaskView):
    """Single protein view: includes needleplot and sequence"""

    cancer_codes = [cancer.code for cancer in Cancer.query.all()]
    populations_1kg = The1000GenomesMutation.populations.values()
    populations_esp = ExomeSequencingMutation.populations.values()
    significances = ClinicalData.significance_codes.values()

    filter_manager = FilterManager(
        [
            Filter(
                Mutation, 'sources', comparators=['in'],
                choices=list(Mutation.source_fields.keys()),
                default='TCGA', nullable=False,
            ),
            Filter(
                Mutation, 'is_ptm', comparators=['eq']
            ),
            Filter(
                Site, 'type', comparators=['in'],
                choices=[
                    'phosphorylation', 'acetylation',
                    'ubiquitination', 'methylation'
                ],
            ),
            SourceDependentFilter(
                [Mutation, CancerMutation], 'cancer_code',
                comparators=['in'],
                choices=cancer_codes,
                default=cancer_codes, nullable=False,
                source='TCGA',
                multiple='any',
            ),
            SourceDependentFilter(
                Mutation, 'populations_1KG', comparators=['in'],
                choices=populations_1kg,
                default=populations_1kg, nullable=False,
                source='1KGenomes',
                multiple='any',
            ),
            SourceDependentFilter(
                Mutation, 'populations_ESP6500', comparators=['in'],
                choices=populations_esp,
                default=populations_esp, nullable=False,
                source='ESP6500',
                multiple='any',
            ),
            SourceDependentFilter(
                [Mutation, ClinicalData], 'significance', comparators=['in'],
                choices=significances,
                default=significances, nullable=False,
                source='ClinVar',
                multiple='any',
            )
        ]
    )

    filter_widgets = [
        FilterWidget(
            'Source', 'select',
            filter=filter_manager.filters['Mutation.sources'],
            labels=[
                'Cancer (TCGA)',
                'Clinical (ClinVar)',
                'Population (ESP 6500)',
                'Population (1000 Genomes)'
            ]
        ),
        FilterWidget(
            'PTM mutations', 'with_without',
            filter=filter_manager.filters['Mutation.is_ptm']
        ),
        FilterWidget(
            'Site type', 'select',
            filter=filter_manager.filters['Site.type']
        ),
        FilterWidget(
            'Cancer', 'select_multiple',
            filter=filter_manager.filters['Mutation.cancer_code'],
            labels=[
                cancer.name + ' (' + cancer.code + ')'
                for cancer in Cancer.query.all()
            ]
        ),
        FilterWidget(
            'Population', 'select_multiple',
            filter=filter_manager.filters['Mutation.populations_1KG'],
            labels=populations_labels(The1000GenomesMutation.populations)
        ),
        FilterWidget(
            'Population', 'select_multiple',
            filter=filter_manager.filters['Mutation.populations_ESP6500'],
            labels=populations_labels(ExomeSequencingMutation.populations)
        ),
        FilterWidget(
            'Clinical significance', 'select_multiple',
            filter=filter_manager.filters['Mutation.significance']
        )
    ]

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
        raw_mutations = self.filter_manager.apply(protein.mutations)

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
            'protein/index.html', protein=protein, tracks=tracks,
            filters=self.filter_manager,
            filter_widgets=self.filter_widgets,
            value_type=value_type,
            log_scale=(value_type == 'Frequency'),
            mutations=parsed_mutations,
            sites=self._prepare_sites(protein),
        )

    def mutations(self, refseq):
        """List of mutations suitable for needleplot library"""

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()

        raw_mutations = self.filter_manager.apply(protein.mutations)
        source = self.filter_manager.get_value('Mutation.sources')

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
        sites = self.filter_manager.apply(protein.sites)
        return [
            {
                'start': site.position - 7,
                'end': site.position + 7,
                'type': str(site.type)
            } for site in sites
        ]

    def _represent_mutations(self, mutations, source, source_field_name):

        response = []

        for mutation in mutations:

            field = getattr(mutation, source_field_name)
            mimp = getattr(mutation, 'meta_MIMP')

            metadata = {
                source: field.to_json(self.filter_manager.apply)
            }

            if mimp:
                metadata['MIMP'] = mimp.to_json()

            closest_sites = mutation.find_closest_sites()

            needle = {
                'coord': mutation.position,
                'value': field.get_value(self.filter_manager.apply),
                'category': mutation.impact_on_ptm,
                'alt': mutation.alt,
                'ref': mutation.ref,
                'meta': metadata,
                'sites': [
                    site.to_json()
                    for site in closest_sites
                ],
                'kinases': [
                    kinase.name
                    for site in closest_sites
                    for kinase in site.kinases
                ] + [
                    kinase.name
                    for site in closest_sites
                    for kinase in site.kinase_groups
                ],
                'cnt_ptm': mutation.cnt_ptm_affected,
                'summary': field.summary,
            }
            response += [needle]

        return response
