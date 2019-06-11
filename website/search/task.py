import pickle
from typing import Dict

from app import celery
from helpers.pickle import pickle_as_str, unpickle_str
from search.mutation import MutationSearch

from search.filters import SearchViewFilters


class SearchTask:

    def __init__(self, vcf_file, textarea_query: str, filter_manager: SearchViewFilters, dataset_uri=None):
        self.vcf_file = vcf_file
        self.textarea_query = textarea_query
        self.filter_manager = filter_manager
        self.dataset_uri = dataset_uri

    def serialize(self) -> Dict:
        return {
            'vcf_file': self.vcf_file,
            'textarea_query': self.textarea_query,
            'filter_manager': pickle_as_str(self.filter_manager),
            'dataset_uri': self.dataset_uri
        }

    @classmethod
    def from_serialized(cls, vcf_file, textarea_query, filter_manager, dataset_uri):
        filter_manager = unpickle_str(filter_manager)

        if not isinstance(filter_manager, SearchViewFilters):
            # print('This weird issue again... Retrying')
            filter_manager = pickle.loads(filter_manager)

        return cls(
            vcf_file,
            textarea_query,
            filter_manager,
            dataset_uri
        )


@celery.task
def search_task(task_data):
    task = SearchTask.from_serialized(**task_data)
    mutation_search = MutationSearch(task.vcf_file, task.textarea_query, task.filter_manager)
    return pickle_as_str(mutation_search), task.dataset_uri
