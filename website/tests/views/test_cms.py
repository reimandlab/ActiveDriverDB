from contextlib import contextmanager
from urllib.parse import quote

from view_testing import ViewTest
from models import Page
from models import Menu
from models import CustomMenuEntry
from models import PageMenuEntry
from database import db


class Flash:
    def __init__(self, content, category):
        self.content = content
        self.category = category

    def __repr__(self):
        return '<Flash %s: %s>' % (self.category, self.content)


class TestCMS(ViewTest):

    invalid_addresses = ['/test/', ' test/', 'test//', '/', '/test']
    weird_addresses = ['test/test', ' /test', ' test', 'test ']

    def is_only_for_admins(self, address):
        response = self.client.get(address)
        if response.status_code == 200:
            return False
        self.login(create=True, admin=False)
        response = self.client.get(address)
        self.logout()
        if response.status_code != 401:
            return False
        return True

    @contextmanager
    def collect_flashes(self):
        flashes = []
        from website.views import cms

        original_flash = cms.flash

        def flash_collector(*args):
            collected_flash = Flash(*args)
            flashes.append(collected_flash)
            original_flash(*args)

        cms.flash = flash_collector

        yield flashes

        cms.flash = original_flash

    @contextmanager
    def assert_flashes(self, *args, **kwargs):
        with self.collect_flashes() as flashes:
            yield
            assert self.assert_flashed(flashes, *args, **kwargs)

    def assert_flashed(self, flashes, content, category=None):
        for flash in flashes:
            if flash.content == content and (not category or flash.category == category):
                return True
        print('Recent flashes: %s' % self.recent_flashes)
        raise AssertionError('No flash: %s, %s' % (content, category))

    def test_admin_only_protection(self):
        from views.cms import admin_only

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

        self.login(email='admin@domain.org', create=True, admin=True)

        # check if form is included in template and if the template renders
        assert '<form method="POST">' in self.client.get('/add/').data

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

        self.login(email='admin@domain.org', create=True, admin=True)

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

        self.login(email='admin@domain.org', create=True, admin=True)

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

    def test_setting(self):
        assert self.is_only_for_admins('/settings/')

    def test_add_menu_entry(self):
        pass

    def test_modify_menu(self):
        assert self.is_only_for_admins('/list_menus/')
