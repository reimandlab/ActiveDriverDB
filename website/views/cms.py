from flask import render_template as template
from flask_classful import FlaskView
from flask_classful import route
from website.models import Page
"""
from flask import request
from flask import jsonify
from flask import redirect
from flask import url_for
"""


class ContentManagmentSystem(FlaskView):

    @route('/<page_name>')
    def page(self, page_name):
        page = Page.query.filter_by(codename=page_name)
        return template('cms/page.html', page=page)

    def show_pages(self, page_name):
        pages = Page.query.all()
        return template('cms/show_page.html', pages=pages)

    def edit_page(self, page_name):
        page = Page.query.filter_by(codename=page_name)
        return template('cms/page.html', page=page)
