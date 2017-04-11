from view_testing import ViewTest
from models import Protein
from database import db
import json
#from flask_testing import assertRedirects


class TestShortUrl(ViewTest):

    def test_get_and_visit(self):

        tested_address = '/some_address'

        # generate a shorthand
        response = self.client.get('/get_shorthand/?address=' + tested_address)

        assert response.status_code == 200
        assert response.content_type == 'application/json'
        shorthand = json.loads(response.data.decode())[0]
        print(shorthand)
        assert shorthand
        db.session.commit()

        # check if generated shorthand works
        response = self.client.get('/s/{0}/'.format(shorthand))

        #assert response.status_code == 200
        self.assertRedirects(response, tested_address)

    def test_is_word_obscene(self):
        from views import short_url
        short_url.list_of_profanities = ['this_should_fail', 'and_this']

        assert not short_url.is_word_obscene('this_is_should_pass')

        should_fail = ['this_should_fail', 'ThI5_Sh0UID_Fail', 'And_thiS']

        for word in should_fail:
            assert short_url.is_word_obscene(word)
