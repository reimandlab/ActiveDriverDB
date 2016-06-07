from flask import Flask
from flask_assets import Environment
from flask_assets import Bundle
from database import db


app = Flask(__name__)
app.config.from_pyfile('config.py')

db.init_app(app)
db.app = app
db.create_all()

"""
Define assets
"""

assets = Environment(app)

bundles = {
    'js_search': Bundle(
        'search.js',
        filters='rjsmin',
        output='search.min.js'
    ),
    'js_protein_view': Bundle(
        'needleplot.js',
        'filters.js',
        'tracks.js',
        filters='rjsmin',
        output='proteinView.min.js'
    ),
    'js_network_view': Bundle(
        'network.js',
        'filters.js',
        filters='rjsmin',
        output='networkView.min.js'
    ),
    'css_common': Bundle(
        'style.css',
        filters='cssutils',
        output='style.min.css'
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

app.register_blueprint(general)

ProteinView.register(app)
NetworkView.register(app)
SearchView.register(app)
