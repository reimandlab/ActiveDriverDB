from flask import Flask
from flask_assets import Environment
from flask_login import LoginManager
from database import db
from database import bdb
from database import bdb_refseq
from assets import bundles

login_manager = LoginManager()


def create_app(config_filename='config.py', config_override={}):
    """Factory function for flask application.

    Args:
        config_filename:
            path to python config file
        config_override:
            a dict with settings to use to override config from file;
            useful for writing very specific tests.
    """
    app = Flask(__name__)

    #
    # Configuration handling
    #

    if config_filename:
        app.config.from_pyfile(config_filename)

    for key, value in config_override.items():
        app.config[key] = value

    #
    # Error logging
    #
    if not app.debug:
        import os
        import logging
        from logging.handlers import RotatingFileHandler

        os.makedirs('logs', exist_ok=True)

        file_handler = RotatingFileHandler(
            'logs/app.log',
            maxBytes=10*1024*1024,
            backupCount=5
        )
        file_handler.setLevel(logging.WARNING)
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)

    #
    # Database creation
    #
    db.app = app
    db.init_app(app)
    db.create_all(bind='__all__')

    bdb.open(app.config['BDB_DNA_TO_PROTEIN_PATH'])
    bdb_refseq.open(app.config['BDB_GENE_TO_ISOFORM_PATH'])

    #
    # Configure Login Manager
    #
    login_manager.init_app(app)

    #
    # Register assets
    #
    assets = Environment(app)

    for name, bundle in bundles.items():
        assets.register(name, bundle)

    #
    # Import views
    #

    # allow access to this app from views through module
    import sys
    sys.path.insert(0, '..')

    with app.app_context():

        from website.views import views

        for view in views:
            view.register(app)

    #
    # Register functions for Jinja
    #

    from website.views.cms import substitute_variables
    from website.views.cms import ContentManagmentSystem
    import json

    # csrf adds hooks in before_request to validate tokens, needs app context
    with app.app_context():
        import csrf

    app.jinja_env.trim_blocks = True
    app.jinja_env.lstrip_blocks = True

    jinja_globals = app.jinja_env.globals
    jinja_filters = app.jinja_env.filters

    jinja_globals['system_menu'] = ContentManagmentSystem._system_menu
    jinja_globals['system_setting'] = ContentManagmentSystem._system_setting
    jinja_globals['csrf_token'] = csrf.new_csrf_token
    jinja_globals['is_debug_mode'] = app.debug

    jinja_filters['json'] = json.dumps
    jinja_filters['substitute_allowed_variables'] = substitute_variables

    return app
