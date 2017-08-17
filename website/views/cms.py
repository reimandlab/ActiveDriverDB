import re
from os import path
from functools import wraps
from pathlib import Path
from types import FunctionType

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
from flask_login import current_user
from flask_login import login_user
from flask_login import logout_user
from flask_login import login_required
from flask_mail import Message
from jinja2 import TemplateSyntaxError
from flask import render_template_string
from werkzeug.utils import secure_filename

from models import Page, HelpEntry, TextEntry
from models import Menu
from models import MenuEntry
from models import PageMenuEntry
from models import CustomMenuEntry
from models import Setting
from models import User
from database import db
from database import get_or_create
from app import login_manager
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.exc import MultipleResultsFound
from sqlalchemy.exc import IntegrityError, OperationalError
from statistics import STATISTICS
from exceptions import ValidationError


BUILT_IN_SETTINGS = ['website_name', 'is_maintenance_mode_active', 'maintenace_text', 'email_sign_up_message']

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


def create_contact_form():
    args = request.args
    pass_args = ['feature', 'title']
    return template(
        'cms/contact_form.html',
        **{key: args.get(key, '') for key in pass_args}
    )


def render_help_entry(entry_id, entry_class=''):
    template = current_app.jinja_env.get_template('help.html')
    module = template.make_module({'current_user': current_user})
    return module.help(entry_id, entry_class)


USER_ACCESSIBLE_VARIABLES = {
    'stats': STATISTICS,
    'contact_form': create_contact_form,
    'help': render_help_entry
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


def update_obj_with_dict(instance, dictionary):
    for key, value in dictionary.items():
        setattr(instance, key, value)


def dict_subset(dictionary, keys):
    return {k: v for k, v in dictionary.items() if k in keys}


def replace_allowed_object(match_obj):
    object_name = match_obj.group(1).strip()
    element = USER_ACCESSIBLE_VARIABLES
    for accessor in object_name.split('.'):
        if accessor in element:
            element = element[accessor]
        else:
            return '&lt;unknown variable: {}&gt;'.format(object_name)
        if type(element) is FunctionType:
            element = element()
    return str(element)


def substitute_variables(string):
    import re
    pattern = '\{\{ (.*?) \}\}'
    try:
        return render_template_string(string, **USER_ACCESSIBLE_VARIABLES)
    except TemplateSyntaxError as e:
        print(e)
        return re.sub(pattern, replace_allowed_object, string)


def link_to_page(page):
    link_title = page.title or '[Page without a title]'
    return html_link(page.address, link_title)


def get_system_setting(name):
    return Setting.query.filter_by(name=name).first()


def thousand_separated_number(x):
    return '{:,}'.format(int(x))


def send_message(**kwargs):
    from app import mail

    msg = Message(
        subject='[ActiveDriverDB] ' + kwargs.pop('subject', 'Message'),
        sender='ActiveDriverDB <contact-bot@activedriverdb.org>',
        **kwargs
    )

    try:
        mail.send(msg)
        flash('Message sent!', 'success')
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
    def send_message(self):
        go_to = request.form.get('after_success', '/')
        redirection = redirect(go_to)

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

        send_message(
            subject=subject,
            body=content,
            recipients=current_app.config['CONTACT_LIST'],
            reply_to='{0} <{1}>'.format(name, email),
        )

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
        try:
            menu = Menu.query.get(menu_id)
            for element, value in request.form.items():
                if element.startswith('position['):
                    entry_id = element[9:-1]
                    entry = MenuEntry.query.get(entry_id)
                    entry.position = float(value)
                if element == 'name':
                    menu.name = value
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

    def activate_account(self):
        args = request.args

        user_id = args['user']
        token = args['token']

        if not (user_id and token):
            raise abort(404)

        user = User.query.get(user_id)

        if token == user.verification_token:

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
    def sign_up(self):
        if request.method == 'GET':
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

            html_message = (
                'Welcome {user.username},\n\n'
                '<p>Thank you for your interest in ActiveDriverDB.'
                'Please use the following link to activate your account:</p>\n\n'
                '<p><a href="{activation_link}" title="Activate your account">{activation_link}</a></p>\n\n'
                '<p>{email_sign_up_message}</p>'
            ).format(
                user=new_user,
                email_sign_up_message=get_system_setting('email_sign_up_message') or '',
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
                html=html_message,
                body=re.sub(r'<[^>]*>', '', html_message)
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
