import re
from urllib.parse import quote, urlparse, urlunparse

from bs4 import BeautifulSoup

from app import mail
from view_testing import ViewTest
from models import Page, User, HelpEntry, Setting
from models import Menu
from models import CustomMenuEntry
from models import PageMenuEntry
from database import db


def find_links(html, **attrs):
    soup = BeautifulSoup(html, 'html.parser')
    return soup.findAll('a', attrs=attrs)


def extract_relative_url(activation_link):
    parsed_url = urlparse(activation_link)
    relative_url = ['', '']
    relative_url.extend(parsed_url[2:])
    path = urlunparse(relative_url)
    return path


def replace_token(path, new_token='some_dummy_token'):
    replaced_token_path = re.sub('token=.*?(&|$)', 'token=%s&' % new_token, path)
    return replaced_token_path


def create_fresh_test_user():
    user = User(email='user@gmail.com', password='strongPassword')
    db.session.add(user)
    db.session.commit()
    return user


class TestCMS(ViewTest):

    invalid_addresses = ['/test/', ' test/', 'test//', '/', '/test']
    weird_addresses = ['test/test', ' /test', ' test', 'test ']

    def view_module(self):
        from website.views import cms
        return cms

    def login_as_admin(self):
        self.login(email='admin@domain.org', create=True, admin=True)

    def is_only_for_admins(self, address, method='get'):
        if method == 'get':
            tester = self.client.get
        else:
            tester = self.client.post

        response = tester(address)
        if response.status_code == 200:
            return False
        self.login(create=True, admin=False)
        response = tester(address)
        self.logout()
        if response.status_code != 401:
            return False
        return True

    def test_admin_only_protection(self):
        from views.cms import admin_only

        # TODO use PREFERRED_URL_SCHEME?
        host = 'http://localhost'

        @self.app.route('/secret')
        @admin_only
        def secret():
            return 'secret content'

        # redirect to login page when user not logged in
        response = self.client.get('/secret')
        expected_address = host + '/login/?next=' + quote(host + '/secret', safe='')
        self.assertRedirects(response, expected_address)

        # forbidden for non-admins
        self.login('user@domain.org', 'password', create=True, admin=False)
        response = self.client.get('/secret')
        assert response.status_code == 401
        self.logout()

        # allowed for admins
        self.login('admin@domain.org', 'password', create=True, admin=True)
        response = self.client.get('/secret')
        assert response.status_code == 200
        assert response.data.decode('utf-8') == 'secret content'
        self.logout()

        assert self.is_only_for_admins('/secret')

    def test_add_page(self):
        assert self.is_only_for_admins('/add/')

        def add_page(**data):
            return self.client.post(
                '/add/',
                data=data,
                follow_redirects=True
            )

        self.login_as_admin()

        # check if form is included in template and if the template renders
        assert b'<form method="POST">' in self.client.get('/add/').data

        # test adding a simple page
        response = add_page(title='Test', address='test')
        assert response.status_code == 200
        page = Page.query.filter_by(address='test').one()
        assert page and page.title == 'Test'

        # no address given
        with self.assert_flashes('Address cannot be empty'):
            add_page(title='Test', address='')

        # existing address
        with self.assert_flashes('Page with address: "test" already exists.'):
            add_page(title='Test', address='test')

        # invalid address
        for invalid_address in self.invalid_addresses:
            with self.assert_flashes('Address cannot contain neither consecutive nor trailing slashes'):
                add_page(address=invalid_address)

        # valid but unusual
        for weird_address in self.weird_addresses:
            title = 'weird test: ' + weird_address
            add_page(title=title, address=weird_address)
            assert response.status_code == 200
            page = Page.query.filter_by(address=weird_address).one()
            assert page and page.title == title

        self.logout()

    def test_show_page(self):
        # normal page
        page = Page(title='My page', content='My text', address='my-page')
        db.session.add(page)
        with self.collect_flashes() as flashes:
            response = self.client.get('my-page/')
            assert b'My page' in response.data
            assert b'My text' in response.data
            assert not flashes

        # routing - valid but unusual addresses
        for weird_address in self.weird_addresses:
            page = Page(address=weird_address)
            db.session.add(page)

            with self.collect_flashes() as flashes:
                response = self.client.get(weird_address + '/')
                assert response.status_code == 200
                assert not flashes

    def test_edit_page(self):
        page = Page(title='test title', address='test_page', content='test content')
        db.session.add(page)
        assert self.is_only_for_admins('/edit/test_page/')

        self.login_as_admin()

        response = self.client.get('/edit/test_page/')
        assert response.status_code == 200

        # title and content edit
        new_data = {
            'address': 'changed_address',
            'title': 'changed title',
            'content': 'changed content'
        }
        self.client.post('/edit/test_page/', data=new_data, follow_redirects=True)
        assert page.address == new_data['address']
        assert page.title == new_data['title']
        assert page.content == new_data['content']

        with self.assert_flashes('Address cannot be empty'):
            response = self.client.post(
                '/edit/changed_address/',
                data={
                    'address': '',
                    'content': 'I accidentally removed address but want the content preserved!'
                },
                follow_redirects=True
            )
            # user should get their edited text back (no one likes to loose his work)
            assert b'I accidentally removed address but want the content preserved!' in response.data
            # but the actual text should not be changed
            assert page.content == 'changed content'
            assert page.address == 'changed_address'

        # weird addresses
        for weird_address in self.weird_addresses:
            page = Page(address=weird_address)
            db.session.add(page)

            response = self.client.post('/edit/' + weird_address + '/', data={'title': 'new title'})
            assert response.status_code == 200
            assert page.title == 'new title'

        self.logout()

    def test_remove_page(self):
        page = Page(address='test_page')
        db.session.add(page)
        assert self.is_only_for_admins('/remove_page/test_page/')

        self.login_as_admin()

        # weird addresses
        for weird_address in self.weird_addresses:
            page = Page(address=weird_address)
            db.session.add(page)

            response = self.client.get('/remove_page/' + weird_address + '/', follow_redirects=True)
            assert response.status_code == 200

            assert Page.query.filter_by(address=weird_address).count() == 0

        self.logout()

    def test_list_pages(self):
        assert self.is_only_for_admins('/list_pages/')

        self.login_as_admin()

        response = self.client.get('/list_pages/')
        assert b'MyTestPage' not in response.data

        page = Page(title='MyTestPage', address='test', content='some')
        db.session.add(page)

        response = self.client.get('/list_pages/')
        assert b'MyTestPage' in response.data
        self.logout()

    def test_inline_help(self):
        help = HelpEntry(name='my-helpful-hint', content='Reading help messages may help you')
        db.session.add(help)

        from views import ContentManagementSystem
        assert ContentManagementSystem._inline_help('my-helpful-hint') == help.content

    def test_render_inline_help(self):
        db.session.add(
            HelpEntry(name='helpful-hint', content='Some explanation')
        )

        page = Page(
            content='Some not so obvious statement {{ help("helpful-hint") }}',
            address='test-help'
        )
        db.session.add(page)

        response = self.client.get('/test-help/')

        assert b'Some not so obvious statement' in response.data
        assert b'Some explanation' in response.data

    def test_save_inline_help(self):
        assert self.is_only_for_admins('/admin/save_inline_help/', method='post')

        self.login_as_admin()

        # new entry
        data = {'entry_id': 'new-help', 'new_content': 'Some helpful text.'}
        response = self.client.post('/admin/save_inline_help/', data=data, follow_redirects=True)
        assert response.json['status'] == 200
        entry = HelpEntry.query.filter_by(name='new-help').one()
        assert entry.content == data['new_content']

        # editing old entry
        data['old_content'] = data['new_content']
        data['new_content'] = 'Less helpful msg.'
        self.client.post('/admin/save_inline_help/', data=data, follow_redirects=True)
        assert entry.content == 'Less helpful msg.'

    def test_settings(self):
        assert self.is_only_for_admins('/settings/')
        s = Setting(name='copyright', value='Authors 2000')
        db.session.add(s)

        from flask import render_template_string
        test_use = render_template_string('{{ system_setting("copyright") }}')
        assert test_use == s.value

        self.login_as_admin()

        response = self.client.get('/settings/')
        html = response.data.decode('utf-8')
        assert s.name in html and s.value in html

        self.logout()

    def save_setting(self):
        assert self.is_only_for_admins('/settings/save/', method='post')

    def test_add_menu(self):
        assert self.is_only_for_admins('/add_menu/', method='post')

        self.login_as_admin()

        # error handling
        with self.assert_flashes('Menu name is required'):
            self.client.post('/add_menu/', data={'name': ''}, follow_redirects=True)

        # menu adding
        self.client.post('/add_menu/', data={'name': 'My menu'})
        assert len(Menu.query.filter_by(name='My menu').all()) == 1

        # prevent duplicates
        with self.collect_flashes() as flashes:
            self.client.post('/add_menu/', data={'name': 'My menu'}, follow_redirects=True)
            assert 'already exists' in flashes[0].content

        self.logout()

    def test_add_page_menu_entry(self):
        assert self.is_only_for_admins('/menu/0/add_page_menu_entry/', method='post')

        menu = Menu(name='My name')
        page = Page(title='My page', address='my_address')
        db.session.add_all([menu, page])
        db.session.commit()

        self.login_as_admin()

        self.client.post(
            '/menu/%s/add_page_menu_entry/' % menu.id,
            data={'page_id': page.id},
            follow_redirects=True
        )

        entries = PageMenuEntry.query.filter_by(menu_id=menu.id).all()
        assert len(entries) == 1
        assert entries[0].page == page

        self.logout()

    def test_add_custom_menu_entry(self):
        assert self.is_only_for_admins('/menu/0/add_custom_menu_entry/', method='post')

        self.login_as_admin()

        menu = Menu(name='My name')
        db.session.add(menu)
        db.session.commit()

        response = self.client.post(
            '/menu/%s/add_custom_menu_entry/' % menu.id,
            data={
                'title': 'ActiveDriverDB repository',
                'url': 'https://github.com/reimandlab/ActiveDriverDB'
            },
            follow_redirects=True
        )
        assert response.status_code == 200

        entries = CustomMenuEntry.query.filter_by(menu_id=menu.id).all()
        assert len(entries) == 1
        assert entries[0].title == 'ActiveDriverDB repository'
        assert entries[0].url == 'https://github.com/reimandlab/ActiveDriverDB'

        relative_entry = CustomMenuEntry(title='Relative entry', address='/search/protein/')
        assert relative_entry.url == '/search/protein/'

        self.logout()

    def test_remove_menu(self):
        assert self.is_only_for_admins('/remove_menu/0')

        menu = Menu(name='Some menu')
        db.session.add(menu)
        db.session.commit()

        self.login_as_admin()

        m_id = menu.id
        assert Menu.query.get(m_id) == menu
        self.client.get('/remove_menu/%s' % m_id)
        assert Menu.query.get(m_id) is None

        self.logout()

    def test_modify_menu(self):
        assert self.is_only_for_admins('/list_menus/')

    def activation_test(self, user, activation_mail, data):
        from views.cms import ACCOUNT_ACTIVATED_MESSAGE

        # take the link from html version of message:
        activation_links = find_links(activation_mail.html, title='Activate your account')

        assert len(activation_links) == 1
        activation_link = activation_links[0].attrs['href']

        # activation link should be an external URL, no relative one
        assert activation_link.startswith('http')

        # compare with link from html-stripped, plain version
        plain_link = re.search(r'(http://.*?)\s', activation_mail.body).group(1)
        assert plain_link == activation_link

        # is the user not verified yet?
        assert not user.is_verified

        # user should NOT be able to log-in before verifying their account:
        assert not user.authenticate(data['password'])

        path = extract_relative_url(activation_link)

        # invalid token should not activate the account
        replaced_token_path = replace_token(path)
        response = self.client.get(replaced_token_path, follow_redirects=True)
        assert response.status_code == 404
        assert not user.is_verified

        # is the activation link working?
        with self.assert_flashes(ACCOUNT_ACTIVATED_MESSAGE, category='success'):
            self.client.get(path, follow_redirects=True)
        assert user.is_verified

        # user should be able to log-in now:
        assert user.authenticate(data['password'])

        # user should be notified if they attempt to activate their account again
        with self.assert_flashes('You account is already active.'):
            self.client.get(path, follow_redirects=True)

    def test_sign_up(self):
        from website.views.cms import SIGNED_UP_OR_ALREADY_USER_MSG

        response = self.client.get('/register/')
        required_fields = ('email', 'password', 'consent')
        for field in required_fields:
            assert bytes('name="%s"' % field, 'utf-8') in response.data

        data = {
            'email': 'user@gmail.com',
            'password': 'strongPassword',
            'consent': True
        }

        with mail.record_messages() as outbox:
            with self.assert_flashes(SIGNED_UP_OR_ALREADY_USER_MSG, category='success'):
                self.client.post('/register/', data=data, follow_redirects=True)

        # was verification email send?
        assert len(outbox) == 1

        sent_mail = outbox[0]
        assert sent_mail.recipients == [data['email']]

        # was a new user created?
        user = User.query.filter_by(email='user@gmail.com').one()
        assert user
        assert not user.is_admin

        # there is a one new user
        assert User.query.count() == 1

        self.activation_test(user, sent_mail, data)

        # Test registration attempt using an email address that already exists in database

        old_password = data['password']
        data['password'] = 'otherPassword2'

        # using an email that exists in our database should not reveal such a fact
        with self.assert_flashes(SIGNED_UP_OR_ALREADY_USER_MSG, category='success'):
            self.client.post('/register/', data=data, follow_redirects=True)

        # nor a new account should be created
        assert User.query.count() == 1

        # nor the old account should be changed
        assert not user.authenticate(data['password'])
        assert user.authenticate(old_password)

        # Test registration without consent
        del data['consent']
        with self.assert_flashes('Data policy consent is required to proceed.'):
            self.client.post('/register/', data=data, follow_redirects=True)

    def test_login(self):
        # using an email that exists in our database should not reveal such a fact
        incorrect_login_message = (
            'Incorrect email or password or unverified account.'
        )
        user = create_fresh_test_user()

        data = {'email': 'user@gmail.com', 'password': 'strongPassword'}

        from flask_login import current_user

        # Test unverified user (users by default should be unverified)
        with self.assert_flashes(incorrect_login_message):
            with self.client:
                self.client.post('/login/', data=data, follow_redirects=True)
                assert current_user != user

        # Test successful login
        user.is_verified = True

        with self.collect_flashes() as flashes:
            with self.client:
                response = self.client.post('/login/', data=data, follow_redirects=True)
                assert response.status_code == 200
                assert not flashes
                assert current_user == user

        # Test logout
        with self.client:
            self.client.get('/logout/', follow_redirects=True)
            assert current_user != user

        # Test incorrect password
        data['password'] = 'strong'
        with self.assert_flashes(incorrect_login_message):
            self.client.post('/login/', data=data, follow_redirects=True)

        # Test incorrect email
        data = {'email': 'u@g.com', 'password': 'strongPassword'}
        with self.assert_flashes(incorrect_login_message):
            self.client.post('/login/', data=data, follow_redirects=True)

    def test_get_page(self):
        from website.views.cms import get_page

        page = Page(title='MyTestPage', address='test', content='some')
        db.session.add(page)
        assert page == get_page('test')

        with self.collect_flashes() as flashes:
            get_page('not-existing-page')
            assert len(flashes) == 1
            assert 'no such a page' in flashes[0].content

    def assert_form_not_accessible(self, faulty_path):
        for method in [self.client.get, self.client.post]:
            response = method(faulty_path, follow_redirects=True)
            assert response.status_code != 200

    def assert_set_password_form_works(self, user, path, check_token=False):
        # correct token should result in form generation
        response = self.client.get(path, follow_redirects=True)
        for field_name in ['password', 'confirm_password']:
            assert BeautifulSoup(response.data, 'html.parser').select_one('input[name="%s"]' % field_name)

        data_validation = {
            'Provided passwords do not match!': ['someStrongPassword', 'ehmIAlreadyForgot..'],
            'Both fields are required.': ['', ''],
            'Provided password is too weak. Please try a different one.': ['so', 'so'],
        }

        # and, as long as 'password' and 'confirm_password' exists, match and are strong enough,
        for expected_flash, data in data_validation.items():
            password, confirmation = data
            data = {'password': password, 'confirm_password': confirmation}

            with self.assert_flashes(expected_flash):
                self.client.post(path, data=data, follow_redirects=True)
                # authentication with the wrong password should not be possible
                assert not user.authenticate(password)
                # token is still there
                if check_token:
                    assert user.verification_token

        data = {'password': 'MySuperStrongPassword', 'confirm_password': 'MySuperStrongPassword'}

        # the user's response should result in password change and token invalidation
        with self.assert_flashes('Your new password has been set successfully!'):
            self.client.post(path, data=data, follow_redirects=True)
        assert user.authenticate(data['password'])
        if check_token:
            assert not user.verification_token

    def test_password_reset(self):
        from views.cms import PASSWORD_RESET_MAIL_SENT
        user = create_fresh_test_user()

        data = {'email': 'user@gmail.com'}

        # is the form working? does it include email input?
        response = self.client.get('/reset_password/')
        assert response.status_code == 200
        assert BeautifulSoup(response.data, 'html.parser').select_one('input[name="email"]')

        # the user is unverified but wait, we don't want to disclose that they even exists!
        # we should claim that mail was sent (but it should not be sent)
        with self.assert_flashes(PASSWORD_RESET_MAIL_SENT):
            with mail.record_messages() as outbox:
                self.client.post('/reset_password/', data=data, follow_redirects=True)
                assert not outbox

        # the same - but for verified user - should result in actual mail being sent
        user.is_verified = True
        with self.assert_flashes(PASSWORD_RESET_MAIL_SENT):
            with mail.record_messages() as outbox:
                self.client.post('/reset_password/', data=data, follow_redirects=True)
                reset_mail = outbox[0]
                assert reset_mail

        # and the user should be able to reset password, using a link provided in email message:
        link = find_links(reset_mail.html, title='Reset password')[0].attrs['href']
        path = extract_relative_url(link)

        # fake token should not work (for both: password setting [post] and form request [get])
        replaced_token_path = replace_token(path)
        self.assert_form_not_accessible(replaced_token_path)

        self.assert_set_password_form_works(user, path, check_token=True)

    def test_change_password(self):
        user = create_fresh_test_user()

        user.is_verified = True

        # unauthenticated user should not be allowed
        self.assert_form_not_accessible('/set_password/')

        self.login(email=user.email, password='strongPassword')

        # for authenticated user the form should work
        self.assert_set_password_form_works(user, '/set_password/', check_token=False)
