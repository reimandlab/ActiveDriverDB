from view_testing import ViewTest


test_query = "chr18 19282310 T C"


class TestSearchView(ViewTest):

    def search_mutations(self, **data):
        return self.client.post(
            '/search/mutations',
            data=data
        )

    def test_save_search(self):

        self.login('user@domain.org', 'password', create=True)

        save_response = self.search_mutations(
            mutations=test_query,
            store_on_server=True,
            dataset_name='Test Dataset'
        )

        assert save_response.status_code == 200

        # if user saved a dataset, it should be listed in his datasets
        browse_response = self.client.get('/my_datasets/')
        assert b'Test Dataset' in browse_response.data

        self.logout()

        # it's still allowed to save data on server without logging in,
        # but then user will not be able to browse these as datasets.
        unauthorized_save_response = self.search_mutations(
            mutations=test_query,
            store_on_server=True,
            dataset_name='Test Dataset'
        )

        assert unauthorized_save_response.status_code == 200
