from flask import render_template as template, Blueprint

general = Blueprint('general', __name__)

@general.route('/')
def index():
    return template('index.html')
