from copy import copy

from view_testing import ViewTest


class TestMail(ViewTest):

    def test_create_contact_form(self):
        from views.cms import create_contact_form

        form = create_contact_form()
        required = (
            # elements
            'submit', 'form',
            # fields
            'email', 'content', 'subject', 'name'
        )
        for required_str in required:
            assert required_str in form

    def test_send_message(self):
        from app import mail

        # easy case: everything is fine
        data = {
            'subject': 'Regarding some mutation',
            'content': 'Some text',
            'name': 'John Doe',
            'email': 'john.doe@domain.org'
        }
        with mail.record_messages() as outbox:
            response = self.client.post(
                '/send_message/',
                data=data,
                follow_redirects=True
            )
            assert response.status_code == 200
            assert b'success' in response.data

            assert len(outbox) == 1

            sent_mail = outbox[0]
            assert sent_mail.subject == data['subject']
            assert sent_mail.body == data['content']
            assert data['email'] in sent_mail.reply_to

        # some failing cases:

        # empties
        failing_cases = {
            key: '' for key in data.keys()
        }
        failing_cases['email'] = 'bad-address'

        for key, value in failing_cases.items():
            wrong_data = copy(data)
            wrong_data[key] = value

            with mail.record_messages() as outbox:
                response = self.client.post('/send_message/', data=wrong_data, follow_redirects=True)
                assert not outbox

            assert b'success' not in response.data

            if key == 'email' and value:
                assert b'email address is not correct' in response.data

