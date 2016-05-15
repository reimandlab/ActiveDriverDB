from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_assets import Environment, Bundle


app = Flask(__name__)
app.config.from_pyfile('config.py')


db = SQLAlchemy(app)


"""
Define assets
"""

assets = Environment(app)

js_search = Bundle(
    'search.js',
    filters='rjsmin',
    output='search.min.js'
)

js_needleplot = Bundle(
    'needleplot.js',
    filters='rjsmin',
    output='needleplot.min.js'
)

css_common = Bundle(
    'style.css',
    filters='cssutils',
    output='style.min.css'
)

assets.register('js_search', js_search)
assets.register('js_needleplot', js_needleplot)
assets.register('css_common', css_common)


"""
Register functions for Jinja
"""

import csrf
import json

app.jinja_env.lstrip_blocks = True

app.jinja_env.globals['csrf_token'] = csrf.new_csrf_token

app.jinja_env.filters['json'] = json.dumps

"""
Import viwes
"""

import views
