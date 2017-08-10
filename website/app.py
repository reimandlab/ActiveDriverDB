import os
from flask import Flask
from flask_assets import Environment
from flask_login import LoginManager

import csrf
from database import db, get_engine
from database import bdb
from database import bdb_refseq
from assets import bundles
from assets import DependencyManager
from flask_mail import Mail

login_manager = LoginManager()
mail = Mail()


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

    if app.config['USE_LEVENSTHEIN_MYSQL_UDF']:
        with app.app_context():
            for bind_key in ['bio', 'cms']:
                engine = get_engine(bind_key)
                engine.execute("DROP FUNCTION IF EXISTS levenshtein_ratio")
                engine.execute("CREATE FUNCTION levenshtein_ratio RETURNS REAL SONAME 'levenshtein.so'")

    #
    # Configure Login Manager
    #
    from models import User
    from models import AnonymousUser

    login_manager.anonymous_user = AnonymousUser
    login_manager.user_loader(User.user_loader)

    login_manager.init_app(app)

    #
    # Configure mail service
    #
    mail.init_app(app)

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

    import jinja2

    base_dir = os.path.dirname(os.path.realpath(__file__))

    template_loader = jinja2.ChoiceLoader([
        app.jinja_loader,
        jinja2.FileSystemLoader(os.path.join(base_dir, 'static/js_templates')),
    ])
    app.jinja_loader = template_loader

    from website.views.cms import substitute_variables
    from website.views.cms import thousand_separated_number
    from website.views.cms import ContentManagementSystem
    from jinja2_pluralize import pluralize
    import json

    # csrf adds hooks in before_request to validate token
    app.before_request(csrf.csrf_protect)

    app.jinja_env.trim_blocks = True
    app.jinja_env.lstrip_blocks = True

    jinja_globals = app.jinja_env.globals
    jinja_filters = app.jinja_env.filters

    dependency_manager = DependencyManager(app)

    jinja_globals['dependency'] = dependency_manager.get_dependency
    jinja_globals['system_menu'] = ContentManagementSystem._system_menu
    jinja_globals['system_setting'] = ContentManagementSystem._system_setting
    jinja_globals['inline_help'] = ContentManagementSystem._inline_help
    jinja_globals['text_entry'] = ContentManagementSystem._text_entry
    jinja_globals['t_sep'] = thousand_separated_number
    jinja_globals['csrf_token'] = csrf.new_csrf_token
    jinja_globals['is_debug_mode'] = app.debug

    jinja_filters['json'] = json.dumps
    jinja_filters['substitute_allowed_variables'] = substitute_variables
    jinja_filters['pluralize'] = pluralize

    return app
