import re
from os import path
from functools import wraps
from pathlib import Path

from bs4 import BeautifulSoup
from flask import current_app, jsonify
from flask import flash
from flask import render_template as template
from flask import redirect
from flask import request
from flask import url_for
from flask import Markup
from flask import abort
from flask_classful import FlaskView
from flask_classful import route
from flask_limiter.util import get_remote_address
from flask_login import current_user
from flask_login import login_user
from flask_login import logout_user
from flask_login import login_required
from flask_mail import Message
from flask import render_template_string
from werkzeug.utils import secure_filename

import security
import models
from models import Page, HelpEntry, TextEntry
from models import Menu
from models import MenuEntry
from models import PageMenuEntry
from models import CustomMenuEntry
from models import Setting
from models import User
from database import db
from database import get_or_create
from app import login_manager, recaptcha, limiter
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.exc import MultipleResultsFound
from sqlalchemy.exc import IntegrityError, OperationalError
from stats import STORES
from exceptions import ValidationError


BUILT_IN_SETTINGS = [
    'website_name', 'is_maintenance_mode_active', 'maintenace_text',
    'email_sign_up_message', 'footer_text',
]

MENU_SLOT_NAMES = ['footer_menu', 'top_menu', 'side_menu']

SIGNED_UP_OR_ALREADY_USER_MSG = (
    '<b>Your account has been created successfully</b><br>'
    '<p>(Unless you already created an account using this email address: '
    'in such a case your existing account remains intact.<br>'
    'We show the same message for either case in order to protect your privacy and avoid email disclosure)</p>'
    '<p><strong>We sent you a verification email. '
    'Please use a hyperlink included in the email message to activate your account.</strong></p>'
)
ACCOUNT_ACTIVATED_MESSAGE = 'Your account has been successfully activated. You can login in using the form below:'
CAPTCHA_FAILED = 'ReCaptcha verification failed. Please contact use if the message reappears.'
PASSWORD_RESET_MAIL_SENT = (
    'If an account connected to this email address exists (and is verified), '
    'you will receive a password reset message soon'
)


def create_contact_form():
    args = request.args
    pass_args = ['feature', 'title']
    return Markup(template(
        'cms/contact_form.html',
        **{key: args.get(key, '') for key in pass_args}
    ))


def render_raw_template(template_name, *args, **kwargs):
    jinja_template = current_app.jinja_env.get_template(template_name)
    return jinja_template.render(*args, **kwargs)


def get_jinja_macro(template_path, macro_name):
    jinja_template = current_app.jinja_env.get_template(template_path)
    jinja_module = jinja_template.make_module({'current_user': current_user})
    return getattr(jinja_module, macro_name)


def render_help_entry(entry_id, entry_class=''):
    help_macro = get_jinja_macro('help.html', 'help')
    return help_macro(entry_id, entry_class)


def plot_factory(plot_name, macro_name, store_name):
    store = STORES[store_name]

    def plot(name, *args, **kwargs):
        try:
            data = store[name]
        except KeyError:
            return f'<- failed to load {name} {plot_name} ->'
        macro = get_jinja_macro('plots.html', macro_name)
        return macro(name, data, *args, **kwargs)

        # return Markup(render_template_string(
    return plot


def dependency(name):
    return current_app.dependency_manager.get_dependency(name)


USER_ACCESSIBLE_VARIABLES = {
    'stats': STORES['Statistics'],
    'venn': plot_factory('Venn diagram', 'venn', 'VennDiagrams'),
    'box_plot': plot_factory('BoxPlot', 'box_plot', 'Plots'),
    'bar_plot': plot_factory('BarPlot', 'bar_plot', 'Plots'),
    'plot_data': lambda name: STORES['Plots'][name],
    'contact_form': create_contact_form,
    'dependency': dependency,
    'help': render_help_entry,
     # cms models are not exposed on purpose
    'bio_models': models.bio
}


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for(
                'ContentManagementSystem:login',
                next=request.url
            ))
        if not current_user.is_admin:
            abort(401)
        return f(*args, **kwargs)
    return decorated_function


def moderator_or_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for(
                'ContentManagementSystem:login',
                next=request.url
            ))
        if current_user.access_level < 5:
            abort(401)
        return f(*args, **kwargs)
    return decorated_function


def html_link(address, content):
    return '<a href="/{0}">{1}</a>'.format(address, content)


def get_page(address, operation=''):
    if operation:
        operation += ' failed: '

    if not address:
        flash('Address cannot be empty', 'warning')
        return None

    try:
        return Page.query.filter_by(address=address).one()
    except NoResultFound:
        flash(
            operation + 'no such a page: /' + address,
            'warning'
        )
    except MultipleResultsFound:
        flash(
            operation + 'multiple results found for page: /' + address +
            ' Manual check of the database is required',
            'danger'
        )
    return None


def get_form_email_or_ip():
    return request.form.get('email', get_remote_address())


def update_obj_with_dict(instance, dictionary):
    for key, value in dictionary.items():
        setattr(instance, key, value)


def dict_subset(dictionary, keys):
    return {k: v for k, v in dictionary.items() if k in keys}


def substitute_variables(string):
    return render_template_string(string, **USER_ACCESSIBLE_VARIABLES)


def link_to_page(page):
    link_title = page.title or '[Page without a title]'
    return html_link(page.address, link_title)


def get_system_setting(name):
    return Setting.query.filter_by(name=name).first()


def thousand_separated_number(x):
    return '{:,}'.format(int(x))


def send_message(**kwargs):
    from app import mail

    body = kwargs.pop('body', None)
    html = kwargs.pop('html', None)

    if html and not body:
        soup = BeautifulSoup(html)
        for link in soup.select('a'):
            link.append(': ' + link.attrs['href'])
            link.unwrap()
        body = soup.get_text()

    msg = Message(
        subject='[ActiveDriverDB] ' + kwargs.pop('subject', 'Message'),
        sender='ActiveDriverDB <contact-bot@activedriverdb.org>',
        body=body, html=html,
        **kwargs
    )

    try:
        mail.send(msg)
        return True
    except ConnectionRefusedError:
        flash(
            'Could not sent the message. '
            'Email server refuses connection. '
            'We apologize for the inconvenience.',
            'danger'
        )


class ContentManagementSystem(FlaskView):

    route_base = '/'

    @staticmethod
    def _template(name, **kwargs):
        return template('cms/' + name + '.html', **kwargs)

    @staticmethod
    def _system_menu(name):
        assert name in MENU_SLOT_NAMES
        setting = get_system_setting(name)
        if not setting:
            return {
                'is_active': False,
                'message': Markup('<!-- Menu "' + name + '" is not set --!>')
            }
        menu_id = setting.int_value
        menu = Menu.query.get(menu_id)
        if not menu:
            return {
                'is_active': False,
                'message': Markup('<!-- Menu "' + name + '" not found --!>')
            }
        menu_code = ContentManagementSystem._template('menu', menu=menu)
        return {
            'is_active': True,
            'name': menu.name,
            'as_list': Markup(menu_code)
        }

    @staticmethod
    def _system_setting(name):
        setting = get_system_setting(name)
        if setting:
            return setting.value

    @staticmethod
    def _text_entry(name):
        entry = TextEntry.query.filter_by(name=name).first()
        if not entry or not entry.content:
            if current_user.access_level >= 5:
                return 'Please, click the pencil icon to add text here.'
            return ''
        return entry.content

    @route('/admin/save_text_entry/', methods=['POST'])
    @moderator_or_admin
    def save_text_entry(self):
        name = request.form['entry_id']
        new_content = request.form['new_content']

        text_entry, created = get_or_create(TextEntry, name=name)
        if created:
            db.session.add(text_entry)

        status = 200
        text_entry.content = new_content
        try:
            db.session.commit()
        except (IntegrityError, OperationalError) as e:
            print(e)
            db.session.rollback()
            status = 501

        result = {
            'status': status,
            'content': substitute_variables(text_entry.content)
        }
        return jsonify(result)

    @staticmethod
    def _inline_help(name):
        help_entry = HelpEntry.query.filter_by(name=name).first()
        if not help_entry or not help_entry.content:
            empty = 'This element has no help text defined yet.'
            if current_user.access_level >= 5:
                empty += '\nPlease, click the pencil icon to add help.'
            return empty
        return help_entry.content

    @moderator_or_admin
    def link_list(self):
        pages = Page.query
        return jsonify([{'title': page.title, 'value': page.url} for page in pages])

    @route('/admin/save_inline_help/', methods=['POST'])
    @moderator_or_admin
    def save_inline_help(self):
        name = request.form['entry_id']
        old_content = request.form.get('old_content', None)
        new_content = request.form['new_content']

        help_entry, created = get_or_create(HelpEntry, name=name)
        if created:
            db.session.add(help_entry)

        if created or help_entry.content == old_content:
            status = 200
            help_entry.content = new_content
            try:
                db.session.commit()
            except (IntegrityError, OperationalError) as e:
                print(e)
                db.session.rollback()
                status = 501
        else:
            status = 409

        result = {
            'status': status,
            'content': help_entry.content
        }
        return jsonify(result)

    @route('/')
    def index(self):
        return template('front_page.html')

    @route('/<path:address>/')
    def page(self, address):
        page = get_page(address)
        return self._template('page', page=page)

    @route('/send_message/', methods=['POST'])
    @limiter.limit('60/day,30/hour,5/minute')
    def send_message(self):
        go_to = request.form.get('after_success', '/')
        redirection = redirect(go_to)

        if not recaptcha.verify():
            flash(CAPTCHA_FAILED, 'danger')
            return redirection

        try:
            name = request.form['name']
            email = request.form['email']
            subject = request.form['subject']
            content = request.form['content']
        except KeyError:
            flash('Something gone wrong - not all fields are present!', 'danger')
            return redirection

        if not name or not content or not subject or not email:
            flash('Please, fill in all fields', 'warning')
            return redirection

        if not User.is_mail_correct(email):
            flash('Provided email address is not correct', 'warning')
            return redirection

        success = send_message(
            subject=subject,
            body=content,
            recipients=current_app.config['CONTACT_LIST'],
            reply_to='{0} <{1}>'.format(name, email),
        )

        if success:
            flash('Message sent!', 'success')

        return redirection

    @moderator_or_admin
    def list_pages(self):
        pages = Page.query.all()
        return self._template('admin/pages', entries=pages)

    @admin_only
    def list_menus(self):
        menus = Menu.query.all()
        pages = Page.query.all()

        menu_slots = {
            slot: get_system_setting(slot)
            for slot in MENU_SLOT_NAMES
        }
        return self._template(
            'admin/menu',
            menus=menus,
            pages=pages,
            menu_slots=menu_slots
        )

    @admin_only
    def settings(self):
        settings = {
            setting.name: setting
            for setting in Setting.query.all()
        }
        for setting_name in BUILT_IN_SETTINGS:
            if setting_name not in settings:
                settings[setting_name] = get_system_setting(setting_name)

        return self._template(
            'admin/settings',
            settings=settings
        )

    @route('/add_menu/', methods=['POST'])
    @admin_only
    def add_menu(self):
        try:
            name = request.form['name']

            if not name:
                raise ValidationError('Menu name is required')

            menu = Menu(name=name)
            db.session.add(menu)
            db.session.commit()

            flash('Added new menu: ' + menu.name, 'success')

        except ValidationError as error:
            flash(error.message, 'warning')

        except IntegrityError:
            db.session.rollback()
            flash(
                'Menu with name: ' + menu.name + ' already exists.' +
                ' Please, change the name and try again.',
                'danger'
            )

        return redirect(url_for('ContentManagementSystem:list_menus'))

    @route('/menu/<menu_id>/edit', methods=['POST'])
    @admin_only
    def edit_menu(self, menu_id):

        settings = {
            # regexp => handler
        }

        def setting(handler):
            name = handler.__name__
            regex = re.compile(r'{0}\[(\d+)\]'.format(name))
            settings[regex] = handler

        @setting
        def position(entry, value):
            entry.position = float(value)

        @setting
        def parent(entry, value):
            entry.parent = MenuEntry.query.get(value)

        try:
            menu = Menu.query.get(menu_id)
            for element, value in request.form.items():
                # menu-wise settings
                if element == 'name':
                    menu.name = value
                # element-wise settings
                else:
                    for regex, handler in settings.items():
                        match = regex.match(element)
                        if match:
                            entry_id = match.group(1)
                            entry = MenuEntry.query.get(entry_id)
                            handler(entry, value)

            db.session.commit()
        except ValueError:
            flash('Wrong value for position', 'danger')
        return redirect(url_for('ContentManagementSystem:list_menus'))

    @route('/settings/save/', methods=['POST'])
    @admin_only
    def save_settings(self):
        goto = request.form.get(
            'goto',
            url_for('ContentManagementSystem:settings')
        )
        for name, value in request.form.items():
            if name.startswith('setting['):
                name = name[8:-1]
                setting, is_created = get_or_create(Setting, name=name)
                if is_created:
                    db.session.add(setting)
                setting.value = value

                db.session.commit()
        return redirect(goto)

    @route('/settings/set/<name>', methods=['POST'])
    @admin_only
    def set(self, name):
        value = request.form['value']
        goto = request.form.get(
            'goto',
            url_for('ContentManagementSystem:settings')
        )
        setting, is_created = get_or_create(Setting, name=name)
        if is_created:
            db.session.add(setting)
        setting.value = value

        db.session.commit()
        return redirect(goto)

    @admin_only
    def remove_menu(self, menu_id):
        menu = Menu.query.get(menu_id)
        if menu:
            name, menu_id = menu.name, menu.id
            db.session.delete(menu)
            db.session.commit()
            flash(
                'Successfully removed menu "{0}" (id: {1})'.format(
                    name,
                    menu_id
                ),
                'success'
            )
        return redirect(url_for('ContentManagementSystem:list_menus'))

    @route('/menu/<menu_id>/add_page_menu_entry/', methods=['POST'])
    @admin_only
    def add_page_menu_entry(self, menu_id):
        try:
            page_id = request.form['page_id']
            menu = Menu.query.get(menu_id)
            page = Page.query.get(page_id)
            entry = PageMenuEntry(page=page)
            menu.entries.append(entry)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('Something went wrong.', 'danger')
        return redirect(url_for('ContentManagementSystem:list_menus'))

    @route('/menu/<menu_id>/add_custom_menu_entry/', methods=['POST'])
    @admin_only
    def add_custom_menu_entry(self, menu_id):

        menu = Menu.query.get(menu_id)
        entry = CustomMenuEntry(
            title=request.form['title'],
            url=request.form['url']
        )
        menu.entries.append(entry)
        db.session.commit()

        return redirect(url_for('ContentManagementSystem:list_menus'))

    @admin_only
    def remove_menu_entry(self, menu_id, entry_id):
        menu = Menu.query.get(menu_id)
        entry = MenuEntry.query.get(entry_id)
        menu.entries.remove(entry)
        db.session.delete(entry)
        db.session.commit()
        return redirect(url_for('ContentManagementSystem:list_menus'))

    @route('/add/', methods=['GET', 'POST'])
    @moderator_or_admin
    def add_page(self):
        if request.method == 'GET':
            return self._template(
                'admin/add_page',
            )
        page_data = dict_subset(request.form, Page.columns)

        try:
            address = request.form['address']

            if not address:
                raise ValidationError('Address cannot be empty')

            page = Page(
                **page_data
            )
            db.session.add(page)
            db.session.commit()

            flash(
                'Added new page: ' + link_to_page(page),
                'success'
            )
            return redirect(
                url_for('ContentManagementSystem:edit_page', address=address)
            )

        except ValidationError as error:
            flash(error.message, 'warning')

        except IntegrityError:
            db.session.rollback()
            flash('Something went wrong.', 'danger')

        return self._template(
            'admin/add_page',
            page=page_data
        )

    @route('/edit/<path:address>/', methods=['GET', 'POST'])
    @moderator_or_admin
    def edit_page(self, address):
        page = get_page(address, 'Edit')
        if request.method == 'POST' and page:
            page_new_data = dict_subset(request.form, Page.columns)
            try:
                update_obj_with_dict(page, page_new_data)

                if not page.address:
                    raise ValidationError('Address cannot be empty')

                db.session.commit()
                flash(
                    'Page saved: ' + link_to_page(page),
                    'success'
                )
                if page.address != address:
                    return redirect(
                        url_for(
                            'ContentManagementSystem:edit_page',
                            address=page.address
                        )
                    )

            except ValidationError as error:
                db.session.rollback()
                flash(error.message, 'warning')
                page = page_new_data
            except IntegrityError:
                db.session.rollback()
                flash('Something went wrong.', 'danger')
                page = page_new_data

        return self._template('admin/edit_page', page=page)

    @moderator_or_admin
    @route('/admin/upload/image', methods=['POST'])
    def upload_image(self):
        file_object = request.files['file']
        filename = secure_filename(file_object.filename)

        if filename and filename.split('.')[-1] in current_app.config['UPLOAD_ALLOWED_EXTENSIONS']:
            base = Path(path.dirname(path.dirname(path.realpath(__file__))))

            directory = base / Path(current_app.config['UPLOAD_FOLDER'])

            if not directory.exists():
                directory.mkdir()   # exists_ok in 3.5 >

            file_path = directory / filename
            file_object.save(str(file_path))

            return jsonify({'location': '/' + str(file_path.relative_to(base))})

    @route('/remove_page/<path:address>/')
    @moderator_or_admin
    def remove_page(self, address):
        page = get_page(address, 'Remove')
        if page:
            title, page_id = page.title, page.id
            db.session.delete(page)
            db.session.commit()
            flash(
                'Successfully removed page "{0}" (id: {1})'.format(
                    title,
                    page_id
                ),
                'success'
            )
        return redirect(url_for('ContentManagementSystem:list_pages'))

    @route('/login/', methods=['GET', 'POST'])
    @limiter.limit('200/day,100/hour,20/minute', key_func=get_form_email_or_ip, per_method=True)
    def login(self):
        if request.method == 'GET':
            return self._template('login')

        email = request.form['email']
        password = request.form['password']
        remember_me = 'remember_me' in request.form

        user = User.query.filter_by(email=email).first()

        if user and user.authenticate(password):
            login_user(user, remember=remember_me)
            return redirect(url_for('ContentManagementSystem:my_datasets'))
        else:
            flash('Incorrect email or password or unverified account.', 'danger')
            return redirect(url_for('ContentManagementSystem:login'))

    @route('/reset_password/', methods=['GET', 'POST'])
    @limiter.limit('200/day,100/hour,20/minute', key_func=get_form_email_or_ip, per_method=True)
    def reset_password(self):
        if request.method == 'GET':
            return self._template('reset_password')

        if not recaptcha.verify():
            flash(CAPTCHA_FAILED, 'danger')
            return self._template('reset_password')

        user = User.query.filter_by(email=request.form['email']).first()

        if user and user.is_verified:
            user.verification_token = security.generate_random_token()
            db.session.commit()

            send_message(
                subject='Your password reset request',
                recipients=[user.email],
                html=render_raw_template(
                    'email/password_reset_request.html',
                    user=user,
                    password_reset_link=url_for(
                        'ContentManagementSystem:confirm_password_reset',
                        token=user.verification_token,
                        user=user.id,
                        _external=True
                    )
                )
            )

        flash(PASSWORD_RESET_MAIL_SENT, category='success')
        return redirect(url_for('ContentManagementSystem:login'))

    @route('/confirm_password_reset/', methods=['GET', 'POST'])
    def confirm_password_reset(self):
        args = request.args

        user_id = args['user']
        token = args['token']

        if not (user_id and token):
            raise abort(404)

        user = User.query.get(user_id)

        if user and token == user.verification_token:
            login_user(user)
            flash('Your request has been correctly verified. Please set a new password now:', category='success')
            return self.set_password()
        else:
            raise abort(404)

    @route('/set_password/', methods=['GET', 'POST'])
    @login_required
    def set_password(self):
        user = current_user

        if request.method == 'GET':
            return self._template('set_password')
        else:
            password = request.form['password']
            confirm_password = request.form['confirm_password']

            if not password or not confirm_password:
                flash('Both fields are required.', category='danger')
                return self._template('set_password')

            if password != confirm_password:
                flash('Provided passwords do not match!', category='danger')
                return self._template('set_password')

            if not user.is_password_strong(password):
                flash(
                    'Provided password is too weak. Please try a different one.',
                    category='danger'
                )
                return self._template('set_password')

            user.pass_hash = security.generate_secret_hash(password)
            # invalidate token
            user.verification_token = None
            db.session.commit()
            flash('Your new password has been set successfully!', category='success')

            return redirect(url_for('ContentManagementSystem:login'))

    def activate_account(self):
        args = request.args

        user_id = args['user']
        token = args['token']

        if not (user_id and token):
            raise abort(404)

        user = User.query.get(user_id)

        if user and token == user.verification_token:

            if user.is_verified:
                flash('You account is already active.', category='warning')
            else:
                user.is_verified = True
                db.session.commit()

                flash(ACCOUNT_ACTIVATED_MESSAGE, category='success')

            return redirect(url_for('ContentManagementSystem:login'))
        else:
            raise abort(404)

    @route('/register/', methods=['GET', 'POST'])
    @limiter.limit('50/hour,10/minute')
    def sign_up(self):
        if request.method == 'GET':
            return self._template('register')

        if not recaptcha.verify():
            flash(CAPTCHA_FAILED, 'danger')
            return self._template('register')

        consent = request.form.get('consent', False)

        if not consent:
            flash(
                'Data policy consent is required to proceed.',
                'danger'
            )
            return self._template('register')

        email = request.form.get('email', '')
        password = request.form.get('password', '')

        claim_success = False

        try:
            new_user = User(email, password, access_level=0)
            db.session.add(new_user)
            db.session.commit()

            html_message = render_raw_template(
                'email/registration.html',
                user=new_user,
                email_sign_up_message=self._system_setting('email_sign_up_message') or '',
                activation_link=url_for(
                    'ContentManagementSystem:activate_account',
                    token=new_user.verification_token,
                    user=new_user.id,
                    _external=True
                )
            )

            sent = send_message(
                subject='Your account activation link',
                recipients=[new_user.email],
                html=html_message
            )

            if sent:
                claim_success = True

        except ValidationError as e:
            flash(e.message, 'danger')
            return self._template('register')
        except IntegrityError:
            db.session.rollback()

        already_a_user = User.query.filter_by(email=email).count()

        if already_a_user:
            claim_success = True
        else:
            flash(
                'Something went wrong when creating your account. '
                'If the problem reoccurs please contact us.',
                'danger'
            )

        if claim_success:
            flash(SIGNED_UP_OR_ALREADY_USER_MSG, 'success')
            # TODO: create a dedicated "Thank you, but activate your account now" page?
            return redirect(url_for('ContentManagementSystem:login'))

        return self._template('register')

    @login_required
    def my_datasets(self):
        return self._template('datasets', datasets=current_user.datasets)

    def logout(self):
        logout_user()
        return redirect(request.url_root)
