from flask import request

from helpers.filters import FilterManager, Filter
from models import Mutation, Protein
from search.gene import search_feature_engines

search_features = [engine.name for engine in search_feature_engines]


class Feature:
    """Target class for feature filtering"""
    pass


class Search:
    pass


class SearchViewFilters(FilterManager):

    def __init__(self, **kwargs):

        available_features = search_features
        active_features = set(available_features) - {'summary'}

        filters = [
            # Why default = False? Due to used widget: checkbox.
            # It is not possible to distinguish between user not asking for
            # all mutations (so sending nothing in post, since un-checking it
            # will cause it to be skipped in the form) or user doing nothing

            # Why or? Take a look on table:
            # is_ptm    show all muts (by default only ptm)     include?
            # 0         0                                       0
            # 0         1                                       1
            # 1         0                                       1
            # 1         1                                       1
            Filter(
                Mutation, 'is_ptm', comparators=['or'],
                default=False
            ),
            Filter(
                Protein, 'has_ptm_mutations', comparators=['eq'],
                as_sqlalchemy=True
            ),
            Filter(
                Feature, 'name', comparators=['in'],
                default=list(active_features),
                choices=available_features,
            ),
            Filter(
                Search, 'query', comparators=['eq'],
            ),
        ]
        super().__init__(filters)
        self.update_from_request(request)
