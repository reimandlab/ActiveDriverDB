from helpers.filters import Filter
from view_testing import ViewTest


class TestAbstractProteinView(ViewTest):

    def view_module(self):
        from website.views import abstract_protein
        return abstract_protein

    def test_are_filter_managers_graceful(self):
        from views import ProteinView, SequenceView, NetworkView
        from views.abstract_protein import GracefulFilterManager

        graceful_views = [SequenceView, ProteinView, NetworkView]
        for view in graceful_views:
            assert issubclass(view.filter_class, GracefulFilterManager)

    def test_graceful_manager(self):
        from website.views.abstract_protein import GracefulFilterManager

        class Target:
            __name__ = 'TestModel'

        class Request:
            method = 'GET'

            def __init__(self, args):
                self.args = args

        class TestViewFilters(GracefulFilterManager):

            def __init__(self, request):

                filters = [
                    Filter(
                        Target(), 'property', comparators=['in'],
                        choices=['Value1', "Value2, corrected"],
                        multiple=True
                    )
                ]
                super().__init__(filters)
                self.update_from_request(request)

        with self.assert_flashes(
            content='<i>Value2</i> does not occur in <i>property</i> for this protein and therefore it was left out.',
            category='warning'
        ):
            test_request = Request({
                'filters': "TestModel.property:in:Value1,Value2,'Value2, corrected'"
            })
            TestViewFilters(test_request)
