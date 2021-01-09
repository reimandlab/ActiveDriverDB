import os
from pathlib import Path

from flask import Flask
from flask_apscheduler import APScheduler
from flask_assets import Environment
from flask_login import LoginManager
from flask_recaptcha import ReCaptcha
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import csrf
from database import db, get_engine
from database import bdb
from database import bdb_refseq
from assets import bundles
from assets import DependencyManager
from flask_celery import Celery
from ggplot import register_ggplot_functions

login_manager = LoginManager()
mail = Mail()
recaptcha = ReCaptcha()
limiter = Limiter(key_func=get_remote_address)
scheduler = APScheduler()
celery = Celery()


def setup_logging(path: Path):
    import logging
    from logging.handlers import RotatingFileHandler

    path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        path.as_posix(),
        maxBytes=10 * 1024 * 1024,
        backupCount=5
    )
    file_handler.setLevel(logging.WARNING)
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)


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

    # ReCaptcha
    recaptcha.init_app(app)

    # Limiter
    limiter.init_app(app)

    # Scheduler
    if app.config.get('SCHEDULER_ENABLED', True):
        if scheduler.running:
            scheduler.shutdown()
        scheduler.init_app(app)
        scheduler.start()

    # Celery
    celery.init_app(app)
    from celery.security import setup_security
    setup_security()

    #
    # Error logging
    #
    if not app.debug:
        setup_logging(Path(app.config.get('LOGS_PATH', 'logs/app.log')))

    #
    # Database creation
    #
    db.app = app
    db.init_app(app)
    db.create_all(bind='__all__')

    readonly = app.config.get('HDB_READONLY', False)
    bdb.open(app.config['HDB_DNA_TO_PROTEIN_PATH'], readonly=readonly)
    bdb_refseq.open(app.config['HDB_GENE_TO_ISOFORM_PATH'], readonly=readonly)

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

    load_views = app.config.get('LOAD_VIEWS', True)

    if load_views:
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

    # csrf adds hooks in before_request to validate token
    app.before_request(csrf.csrf_protect)

    app.jinja_env.trim_blocks = True
    app.jinja_env.lstrip_blocks = True

    app.dependency_manager = DependencyManager(app)

    if load_views:
        # TODO: this requires accessing views to load CMS functions;
        #  optimally, the CMS logic would be moved out from views.
        register_jinja_functions(app)

    return app


def register_jinja_functions(app):

    from website.views.cms import substitute_variables
    from website.views.cms import thousand_separated_number
    from website.views.cms import ContentManagementSystem
    from jinja2_pluralize import pluralize
    import json

    jinja_globals = app.jinja_env.globals
    jinja_filters = app.jinja_env.filters

    jinja_globals['dependency'] = app.dependency_manager.get_dependency
    jinja_globals['system_menu'] = ContentManagementSystem._system_menu
    jinja_globals['system_setting'] = ContentManagementSystem._system_setting
    jinja_globals['inline_help'] = ContentManagementSystem._inline_help
    jinja_globals['text_entry'] = ContentManagementSystem._text_entry
    jinja_globals['t_sep'] = thousand_separated_number
    jinja_globals['csrf_token'] = csrf.new_csrf_token
    jinja_globals['is_debug_mode'] = app.debug

    from stats import STORES

    def rename_mutations(df):

        from models import source_manager
        mutation_to_label = {
            mutation_source.name: mutation_source.display_name
            for mutation_source in source_manager.all
        }

        if 'MutationType' in df.columns:
            df['MutationType'] = df['MutationType'].apply(lambda code_name: mutation_to_label.get(code_name, code_name))
        return df

    jinja_globals['datasets'] = {
        key: rename_mutations(value)
        for key, value in STORES['Datasets'].items()
    }
    print(STORES['Datasets'].keys())

    register_ggplot_functions(jinja_globals)

    jinja_filters['json'] = json.dumps
    jinja_filters['substitute_allowed_variables'] = substitute_variables
    jinja_filters['pluralize'] = pluralize
