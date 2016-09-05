from flask import Flask
from flask_assets import Environment
from flask_login import LoginManager
from database import db
from assets import bundles


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
Register assets
"""
assets = Environment(app)

for name, bundle in bundles.items():
    assets.register(name, bundle)


"""
Import viwes
"""

# allow acces to this app from views through module
import sys
sys.path.insert(0, '..')

from website.views import ProteinView, SearchView, NetworkView, GeneView
from website.views import ContentManagmentSystem

GeneView.register(app)
ProteinView.register(app)
NetworkView.register(app)
SearchView.register(app)
ContentManagmentSystem.register(app)


"""
Register functions for Jinja
"""

from website.views.cms import substitute_variables
import csrf
import json

app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True

app.jinja_env.globals['csrf_token'] = csrf.new_csrf_token

app.jinja_env.filters['json'] = json.dumps
app.jinja_env.filters['substitute_allowed_variables'] = substitute_variables
