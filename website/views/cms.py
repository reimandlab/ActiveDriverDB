from flask import render_template as template
from flask_classful import FlaskView
from flask_classful import route
from website.models import Page
from flask import request
"""
from flask import jsonify
from flask import redirect
from flask import url_for
"""


class ContentManagmentSystem(FlaskView):

    def _template(name, **kwargs):
        return template('cms/' + name + '.html', **kwargs)

    @route('/<page_name>')
    def page(self, page_name):
        page = Page.query.filter_by(codename=page_name)
        return self._template('page', page=page)

    def show_pages(self, page_name):
        pages = Page.query.all()
        return self._template('show_page', pages=pages)

    def edit_page(self, page_name):
        page = Page.query.filter_by(codename=page_name)
        return self._template('edit', page=page)

    @route('/save/<page_name>', methods=['POST'])
    def save_page(self, page_name):
        page = Page.query.filter_by(codename=page_name)
        return self._template('edit', page=page, saved=True)
