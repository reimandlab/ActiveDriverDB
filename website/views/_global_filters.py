from models import MC3Mutation
from models import Cancer
from models import Mutation
from models import Site
from models import The1000GenomesMutation
from models import ExomeSequencingMutation
from models import ClinicalData
from database import has_or_any
from helpers.filters import Filter
from helpers.widgets import FilterWidget


def filters_data_view(filter_manager):
    from flask import request
    from flask import render_template
    return {
        'query': filter_manager.url_string() or '',
        'expanded_query': filter_manager.url_string(expanded=True) or '',
        'checksum': request.args.get('checksum', ''),
        'dataset_specific_widgets': render_template(
            'widgets/widget_list.html',
            widgets=create_dataset_specific_widgets(filter_manager.filters),
            collapse=True
        )
    }


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


def sources_to_sa_filter(filter, target):
    """TODO: refactor name to: source_filter_to_sa"""
    return source_to_sa_filter(filter.value, target)


def source_to_sa_filter(source_name, target=Mutation):
    field_name = Mutation.source_fields[source_name]
    field = getattr(target, field_name)
    return has_or_any(field)


class UserMutations:
    pass


def common_filters(
    protein,
    default_source='MC3',
    source_nullable=False,
    custom_datasets_ids=[]
):
    cancer_codes_mc3 = protein.cancer_codes(MC3Mutation) if protein else []

    # Python 3.4: cast keys() to list
    populations_1kg = list(The1000GenomesMutation.populations.values())
    populations_esp = list(ExomeSequencingMutation.populations.values())
    significances = list(ClinicalData.significance_codes.keys())
    disease_names = protein.disease_names if protein else []

    return [
        Filter(
            Mutation, 'sources', comparators=['in'],
            choices=list(Mutation.source_fields.keys()),
            default=default_source, nullable=source_nullable,
            as_sqlalchemy=sources_to_sa_filter
        ),
        Filter(
            UserMutations, 'sources', comparators=['in'],
            choices=list(custom_datasets_ids),
            default=None, nullable=True
        ),
        Filter(
            Mutation, 'is_ptm', comparators=['eq'],
            is_attribute_a_method=True
        ),
        Filter(
            Site, 'type', comparators=['in'],
            choices=Site.types,
            as_sqlalchemy=True
        ),
        SourceDependentFilter(
            [Mutation, MC3Mutation], 'mc3_cancer_code',
            comparators=['in'],
            choices=cancer_codes_mc3,
            default=cancer_codes_mc3, nullable=False,
            source='MC3',
            multiple='any',
            as_sqlalchemy=True
        ),
        SourceDependentFilter(
            Mutation, 'populations_1KG', comparators=['in'],
            choices=populations_1kg,
            default=populations_1kg, nullable=False,
            source='1KGenomes',
            multiple='any'
        ),
        SourceDependentFilter(
            Mutation, 'populations_ESP6500', comparators=['in'],
            choices=populations_esp,
            default=populations_esp, nullable=False,
            source='ESP6500',
            multiple='any',
        ),
        SourceDependentFilter(
            [Mutation, ClinicalData], 'sig_code', comparators=['in'],
            choices=significances,
            default=significances, nullable=False,
            source='ClinVar',
            multiple='any'
        ),
        SourceDependentFilter(
            [Mutation, ClinicalData], 'disease_name', comparators=['in'],
            choices=disease_names,
            default=disease_names, nullable=False,
            source='ClinVar',
            multiple='any'
        )
    ]


def create_dataset_specific_widgets(filters_by_id):
    return [
        FilterWidget(
            'Cancer type', 'checkbox_multiple',
            filter=filters_by_id['Mutation.mc3_cancer_code'],
            labels={
                cancer.code: '%s (%s)' % (cancer.name, cancer.code)
                for cancer in Cancer.query
            },
            all_selected_label='All cancer types'
        ),
        FilterWidget(
            'Ethnicity', 'checkbox_multiple',
            filter=filters_by_id['Mutation.populations_1KG'],
            labels=populations_labels(The1000GenomesMutation.populations),
            all_selected_label='All ethnicities'
        ),
        FilterWidget(
            'Ethnicity', 'checkbox_multiple',
            filter=filters_by_id['Mutation.populations_ESP6500'],
            labels=populations_labels(ExomeSequencingMutation.populations),
            all_selected_label='All ethnicities'
        ),
        FilterWidget(
            'Clinical significance', 'checkbox_multiple',
            filter=filters_by_id['Mutation.sig_code'],
            all_selected_label='All clinical significance classes',
            labels=ClinicalData.significance_codes.values()
        ),
        FilterWidget(
            'Disease name', 'checkbox_multiple',
            filter=filters_by_id['Mutation.disease_name'],
            all_selected_label='All clinical significance classes'
        )
    ]


def create_dataset_labels():
    # map dataset display names to dataset names
    dataset_labels = {
        dataset.name: dataset.display_name
        for dataset in Mutation.source_specific_data
    }
    # hide user's mutations in dataset choice
    # (there is separate widget for that, shown only if there are any user's datasets)
    dataset_labels['user'] = None
    return dataset_labels


def create_widgets(filters_by_id, custom_datasets_names=None):
    """Widgets to be displayed on a bar above visualisation."""

    return {
        'dataset': FilterWidget(
            'Mutation dataset', 'radio',
            filter=filters_by_id['Mutation.sources'],
            labels=create_dataset_labels(),
            class_name='dataset-widget'
        ),
        'custom_dataset': FilterWidget(
            'Custom mutation dataset', 'radio',
            filter=filters_by_id['UserMutations.sources'],
            labels=custom_datasets_names
        ),
        'dataset_specific': create_dataset_specific_widgets(filters_by_id),
        'is_ptm': FilterWidget(
            'PTM mutations only', 'checkbox',
            filter=filters_by_id['Mutation.is_ptm'],
            disabled_label='all mutations',
            labels=['PTM mutations only']
        ),
        'ptm_type': FilterWidget(
            'Type of PTM site', 'radio',
            filter=filters_by_id['Site.type'],
            disabled_label='all sites'
        ),
        'other': []
    }
