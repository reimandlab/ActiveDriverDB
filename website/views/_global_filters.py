from models import CancerMutation
from models import Cancer
from models import Mutation
from models import Site
from models import The1000GenomesMutation
from models import ExomeSequencingMutation
from models import ClinicalData
from website.helpers.filters import Filter
from website.helpers.widgets import FilterWidget


cancer_codes = [cancer.code for cancer in Cancer.query.all()]
populations_1kg = The1000GenomesMutation.populations.values()
populations_esp = ExomeSequencingMutation.populations.values()
significances = ClinicalData.significance_codes.values()


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


def common_filters(default_source='TCGA', source_nullable=False):
    return [
        Filter(
            Mutation, 'sources', comparators=['in'],
            choices=list(Mutation.source_fields.keys()),
            default=default_source, nullable=source_nullable,
        ),
        Filter(
            Mutation, 'is_ptm', comparators=['eq'],
            is_attribute_a_method=True
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


def bar_widgets(filters_by_id):
    """WIdgets to be displayed on a bar above visualisation."""
    return [
        FilterWidget(
            'PTM mutations only', 'checkbox',
            filter=filters_by_id['Mutation.is_ptm'],
            disabled_label='all mutations',
        )
    ]


def box_widgets(filters_by_id):
    """Widgets to be displayed in filter's box."""
    return [
        FilterWidget(
            'Mutation dataset', 'radio',
            filter=filters_by_id['Mutation.sources'],
            labels=[
                'Cancer (TCGA)',
                'Clinical (ClinVar)',
                'Population (ESP 6500)',
                'Population (1000 Genomes)'
            ]
        ),
        FilterWidget(
            'Type of PTM site', 'radio',
            filter=filters_by_id['Site.type'],
            disabled_label='all sites'
        ),
        FilterWidget(
            'Cancer type', 'select_multiple',
            filter=filters_by_id['Mutation.cancer_code'],
            labels=[
                cancer.name + ' (' + cancer.code + ')'
                for cancer in Cancer.query.all()
            ]
        ),
        FilterWidget(
            'Ethnicity', 'select_multiple',
            filter=filters_by_id['Mutation.populations_1KG'],
            labels=populations_labels(The1000GenomesMutation.populations)
        ),
        FilterWidget(
            'Ethnicity', 'select_multiple',
            filter=filters_by_id['Mutation.populations_ESP6500'],
            labels=populations_labels(ExomeSequencingMutation.populations)
        ),
        FilterWidget(
            'Clinical significance', 'select_multiple',
            filter=filters_by_id['Mutation.significance']
        )
    ]
