from flask import flash
from flask import render_template as template
from flask import redirect
from flask import request
from flask import url_for
from flask_classful import FlaskView
from flask_classful import route
from flask_login import login_user
from flask_login import logout_user
from flask_login import login_required
from models import Page
from models import User
from database import db
from app import login_manager
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.exc import MultipleResultsFound
from sqlalchemy.exc import IntegrityError
from statistics import STATISTICS


USER_ACCESSIBLE_VARIABLES = {
    'stats': STATISTICS,
}


PAGE_COLUMNS = ('title', 'address', 'content')


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def html_link(address, content):
    return '<a href="/{0}">{1}</a>'.format(address, content)


def get_page(address, operation=''):
    if operation:
        operation += ' failed: '

    try:
        return Page.query.filter_by(address=address).one()
    except NoResultFound:
        flash(
            operation + 'no such page: /' + address,
            'warning'
        )
    except MultipleResultsFound:
        flash(
            operation + 'multiple results found for page: /' + address +
            'Manual check of the database is required',
            'danger'
        )
    return None


def update_obj_with_dict(instance, dictionary):
    for key, value in dictionary.items():
        setattr(instance, key, value)


def dict_subset(dictionary, keys):
    return {k: v for k, v in dictionary.items() if k in keys}


def replace_allowed_object(match_obj):
    object_name = match_obj.group(1).strip()
    element = USER_ACCESSIBLE_VARIABLES
    for accessor in object_name.split('.'):
        if accessor in element:
            element = element[accessor]
        else:
            return '&lt;unknown variable: {}&gt;'.format(object_name)
    return str(element)


def substitute_variables(string):
    import re
    pattern = '\{\{ (.*?) \}\}'
    return re.sub(pattern, replace_allowed_object, string)


class ContentManagmentSystem(FlaskView):

    route_base = '/'

    def _template(self, name, **kwargs):
        return template('cms/' + name + '.html', **kwargs)

    @route('/')
    def index(self):
        return self.page('index')

    @route('/<address>/')
    def page(self, address):
        page = get_page(address)
        return self._template('page', page=page)

    @login_required
    def list_pages(self):
        pages = Page.query.all()
        return self._template('admin/list', entries=pages, entity_name='Page')

    @route('/add/', methods=['GET', 'POST'])
    @login_required
    def add_page(self):
        if request.method == 'GET':
            return self._template(
                'admin/add_page',
            )
        page_data = dict_subset(request.form, PAGE_COLUMNS)
        try:
            address = request.form['address']
            page = Page(
                **page_data
            )
            db.session.add(page)
            db.session.commit()
            flash(
                'Added new page: ' + html_link(page.address, page.title),
                'success'
            )
            return redirect(
                url_for('ContentManagmentSystem:edit_page', address=address)
            )
        except IntegrityError:
            db.session.rollback()
            flash(
                'Page with address: ' + html_link(address, '/' + address) +
                ' already exists. Please, change the address and try again.',
                'danger'
            )
        return self._template(
            'admin/add_page',
            page=page_data
        )

    @route('/edit/<address>/', methods=['GET', 'POST'])
    @login_required
    def edit_page(self, address):
        page = get_page(address, 'Edit')
        if request.method == 'POST' and page:
            page_new_data = dict_subset(request.form, PAGE_COLUMNS)
            try:
                update_obj_with_dict(page, page_new_data)
                db.session.commit()
                flash(
                    'Page saved: ' + html_link(page.address, page.title),
                    'success'
                )
            except IntegrityError:
                db.session.rollback()
                flash(
                    'Page with address: ' + html_link(
                        page_new_data['address'],
                        '/' + page_new_data['address']
                    ) + ' already exists.' +
                    ' Please, change the address and try saving again.',
                    'danger'
                )
                page = page_new_data
        return self._template('admin/edit_page', page=page)

    @login_required
    def remove_page(self, address):
        page = get_page(address, 'Remove')
        if page:
            title, page_id = page.title, page.id
            db.session.delete(page)
            db.session.commit()
            flash(
                'Successfuly removed page "{0}" (id: {1})'.format(
                    title,
                    page_id
                ),
                'success'
            )
        return redirect(url_for('ContentManagmentSystem:list_pages'))

    @route('/login/', methods=['GET', 'POST'])
    def login(self):
        if request.method == 'GET':
            return self._template('login')

        email = request.form['email']
        password = request.form['password']
        remember_me = 'remember_me' in request.form

        user = User.query.filter_by(email=email).first()

        if user is None:
            flash('Invalid or unregistered email', 'error')
            return redirect(url_for('ContentManagmentSystem:login'))

        if user.authenticate(password):
            login_user(user, remember=remember_me)
            return redirect(url_for('ContentManagmentSystem:list_pages'))
        else:
            flash('Password is invalid', 'error')
            return redirect(url_for('ContentManagmentSystem:login'))

    def logout(self):
        logout_user()
        return redirect(request.url_root)
