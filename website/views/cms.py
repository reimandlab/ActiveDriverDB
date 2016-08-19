from flask import flash
from flask import render_template as template
from flask import redirect
from flask import request
from flask import url_for
from flask_classful import FlaskView
from flask_classful import route
from website.models import Page
from website.models import User
from database import db
from app import login_manager
from flask_login import login_user, logout_user, current_user, login_required
"""
from flask import jsonify
"""


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class ContentManagmentSystem(FlaskView):

    def _template(name, **kwargs):
        return template('cms/' + name + '.html', **kwargs)

    @route('/<page_name>')
    def page(self, page_name):
        page = Page.query.filter_by(codename=page_name)
        return self._template('page', page=page)

    @login_required
    def show_pages(self, page_name):
        pages = Page.query.all()
        return self._template('show_page', pages=pages)

    @login_required
    def edit_page(self, page_name):
        page = Page.query.filter_by(codename=page_name)
        return self._template('edit', page=page)

    @login_required
    def remove_page(self, page_name):
        try:
            page = Page.query.filter_by(codename=page_name).one()
            title, page_id = page.title, page.id
            db.session.delete(page)
            db.session.commit()
            flash('Successfuly removed page', title, '(id:', page_id, ')')
            return redirect(url_for('ContentManagmentSystem:show_pages'))
        except Exception:
            # TODO
            pass

    @route('/save/<page_name>', methods=['POST'])
    @login_required
    def save_page(self, page_name):
        page = Page.query.filter_by(codename=page_name)
        return self._template('edit', page=page, saved=True)

    @route('/login', methods=['GET', 'POST'])
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
            return redirect(url_for('ContentManagmentSystem:show_pages'))
        else:
            flash('Password is invalid', 'error')
            return redirect(url_for('ContentManagmentSystem:login'))
