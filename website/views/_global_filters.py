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


def common_filters():
    return [
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


def common_widgets(common_filters):
    def get_filter(filter_id):
        selected = list(filter(lambda x: x.id == filter_id, common_filters))
        assert len(selected) == 1
        return selected[0]

    return [
        FilterWidget(
            'Source', 'select',
            filter=get_filter('Mutation.sources'),
            labels=[
                'Cancer (TCGA)',
                'Clinical (ClinVar)',
                'Population (ESP 6500)',
                'Population (1000 Genomes)'
            ]
        ),
        FilterWidget(
            'PTM mutations', 'with_without',
            filter=get_filter('Mutation.is_ptm')
        ),
        FilterWidget(
            'Site type', 'select',
            filter=get_filter('Site.type')
        ),
        FilterWidget(
            'Cancer', 'select_multiple',
            filter=get_filter('Mutation.cancer_code'),
            labels=[
                cancer.name + ' (' + cancer.code + ')'
                for cancer in Cancer.query.all()
            ]
        ),
        FilterWidget(
            'Population', 'select_multiple',
            filter=get_filter('Mutation.populations_1KG'),
            labels=populations_labels(The1000GenomesMutation.populations)
        ),
        FilterWidget(
            'Population', 'select_multiple',
            filter=get_filter('Mutation.populations_ESP6500'),
            labels=populations_labels(ExomeSequencingMutation.populations)
        ),
        FilterWidget(
            'Clinical significance', 'select_multiple',
            filter=get_filter('Mutation.significance')
        )
    ]
