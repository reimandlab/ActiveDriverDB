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
"""
from flask import jsonify
"""


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

        address = request.form['address']
        page = Page(
            title=request.form['title'],
            address=address,
            content=request.form['content']
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

    @route('/edit/<address>', methods=['GET', 'POST'])
    @login_required
    def edit_page(self, address):
        page = get_page(address, 'Edit')
        if request.method == 'POST' and page:
            page.title = request.form['title']
            page.address = request.form['address']
            page.content = request.form['content']
            db.session.commit()
            flash(
                'Page saved: ' + html_link(page.address, page.title),
                'success'
            )
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
