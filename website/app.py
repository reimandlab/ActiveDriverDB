from flask import Flask
from flask_assets import Bundle
from flask_assets import Environment
from flask_login import LoginManager
from database import db


app = Flask(__name__)
app.config.from_pyfile('config.py')

db.app = app
db.init_app(app)
db.create_all(bind='__all__')

"""
Configure Login Manager
"""
login_manager = LoginManager()
login_manager.init_app(app)


"""
Define assets
"""
assets = Environment(app)


def css_bundle(name, *args):
    return Bundle(
        *args,
        filters='cssutils',
        output='min/' + name + '.css'
    )


bundles = {
    'js_search': Bundle(
        'search.js',
        filters='rjsmin',
        output='min/search.js'
    ),
    'js_protein_view': Bundle(
        'common.js',
        'needleplot.js',
        'filters.js',
        'tracks.js',
        filters='rjsmin',
        output='min/proteinView.js'
    ),
    'js_network_view': Bundle(
        'common.js',
        'orbits.js',
        'network.js',
        'filters.js',
        filters='rjsmin',
        output='min/networkView.js'
    ),
    'css_common': css_bundle(
        'style',
        'sass/style.css'
    ),
    'css_network': css_bundle(
        'network',
        'sass/network.css',
        'sass/filters.css'
    ),
    'css_protein': css_bundle(
        'protein',
        'sass/protein.css',
        'sass/tracks.css',
        'sass/filters.css'
    ),
    'css_search': css_bundle(
        'search',
        'sass/search.css'
    ),
    'css_page': css_bundle(
        'page',
        'sass/page.css'
    ),
    'css_admin': css_bundle(
        'admin',
        'sass/admin.css'
    )
}

for name, bundle in bundles.items():
    assets.register(name, bundle)


"""
Register functions for Jinja
"""

import csrf
import json

app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True

app.jinja_env.globals['csrf_token'] = csrf.new_csrf_token

app.jinja_env.filters['json'] = json.dumps

"""
Import viwes
"""

# allow acces to this app from views through module
import sys
sys.path.insert(0, '..')

from website.views import general, ProteinView, SearchView, NetworkView
from website.views import ContentManagmentSystem

app.register_blueprint(general)

ProteinView.register(app)
NetworkView.register(app)
SearchView.register(app)
ContentManagmentSystem.register(app)
