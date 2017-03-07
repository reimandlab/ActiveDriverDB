from functools import wraps
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
from models import Page
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
from sqlalchemy.exc import IntegrityError
from statistics import STATISTICS
from exceptions import ValidationError


BUILT_IN_SETTINGS = ['website_name']

MENU_SLOT_NAMES = ['footer_menu', 'top_menu', 'side_menu']

USER_ACCESSIBLE_VARIABLES = {
    'stats': STATISTICS
}

PAGE_COLUMNS = ('title', 'address', 'content')


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for(
                'ContentManagmentSystem:login',
                next=request.url
            ))
        if not current_user.is_admin:
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
            'Manual check of the database is required',
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
    return str(element)


def substitute_variables(string):
    import re
    pattern = '\{\{ (.*?) \}\}'
    return re.sub(pattern, replace_allowed_object, string)


def link_to_page(page):
    link_title = page.title or '[Page without a title]'
    return html_link(page.address, link_title)


def get_system_setting(name):
    return Setting.query.filter_by(name=name).first()


class ContentManagmentSystem(FlaskView):

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
        menu_code = ContentManagmentSystem._template('menu', menu=menu)
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

    @route('/')
    def index(self):
        return self.page('index')

    @route('/<address>/')
    def page(self, address):
        page = get_page(address)
        return self._template('page', page=page)

    @admin_only
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

        return redirect(url_for('ContentManagmentSystem:list_menus'))

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
        return redirect(url_for('ContentManagmentSystem:list_menus'))

    @route('/settings/save/', methods=['POST'])
    @admin_only
    def save_settings(self):
        goto = request.form.get(
            'goto',
            url_for('ContentManagmentSystem:settings')
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
            url_for('ContentManagmentSystem:settings')
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
                'Successfuly removed menu "{0}" (id: {1})'.format(
                    name,
                    menu_id
                ),
                'success'
            )
        return redirect(url_for('ContentManagmentSystem:list_menus'))

    @route('/menu/<menu_id>/add_page_menu_entry', methods=['POST'])
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
            flash('Something went wrong :(', 'danger')
        return redirect(url_for('ContentManagmentSystem:list_menus'))

    @route('/menu/<menu_id>/add_custom_menu_entry', methods=['POST'])
    @admin_only
    def add_custom_menu_entry(self, menu_id):

        menu = Menu.query.get(menu_id)
        entry = CustomMenuEntry(
            title=request.form['title'],
            url=request.form['url']
        )
        menu.entries.append(entry)
        db.session.commit()

        return redirect(url_for('ContentManagmentSystem:list_menus'))

    @admin_only
    def remove_menu_entry(self, menu_id, entry_id):
        menu = Menu.query.get(menu_id)
        entry = MenuEntry.query.get(entry_id)
        menu.entries.remove(entry)
        db.session.delete(entry)
        db.session.commit()
        return redirect(url_for('ContentManagmentSystem:list_menus'))

    @route('/add/', methods=['GET', 'POST'])
    @admin_only
    def add_page(self):
        if request.method == 'GET':
            return self._template(
                'admin/add_page',
            )
        page_data = dict_subset(request.form, PAGE_COLUMNS)

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
                url_for('ContentManagmentSystem:edit_page', address=address)
            )

        except ValidationError as error:
            flash(error.message, 'warning')

        except IntegrityError:
            db.session.rollback()
            flash(
                'Page with address: ' + html_link(address, '/' + address) +
                ' already exists. Please, change the address and try again.',
                'danger'
            )

        return self._template(
            'admin/add_page',
            page=page_data
        )

    @route('/edit/<address>/', methods=['GET', 'POST'])
    @admin_only
    def edit_page(self, address):
        page = get_page(address, 'Edit')
        if request.method == 'POST' and page:
            page_new_data = dict_subset(request.form, PAGE_COLUMNS)
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
                            'ContentManagmentSystem:edit_page',
                            address=page.address
                        )
                    )

            except ValidationError as error:
                flash(error.message, 'warning')

            except IntegrityError:
                db.session.rollback()
                flash(
                    'Page with address: ' + html_link(
                        page_new_data['address'],
                        '/' + page_new_data['address']
                    ) + ' already exists.' +
                    ' Please, change the address and try saving again.',
                    'danger'
                )
                page = page_new_data
        return self._template('admin/edit_page', page=page)

    @admin_only
    def remove_page(self, address):
        page = get_page(address, 'Remove')
        if page:
            title, page_id = page.title, page.id
            db.session.delete(page)
            db.session.commit()
            flash(
                'Successfuly removed page "{0}" (id: {1})'.format(
                    title,
                    page_id
                ),
                'success'
            )
        return redirect(url_for('ContentManagmentSystem:list_pages'))

    @route('/login/', methods=['GET', 'POST'])
    def login(self):
        if request.method == 'GET':
            return self._template('login')

        email = request.form['email']
        password = request.form['password']
        remember_me = 'remember_me' in request.form

        user = User.query.filter_by(email=email).first()

        if user is None:
            flash('Invalid or unregistered email', 'danger')
            return redirect(url_for('ContentManagmentSystem:login'))

        if user.authenticate(password):
            login_user(user, remember=remember_me)
            return redirect(url_for('ContentManagmentSystem:my_datasets'))
        else:
            flash('Password is invalid', 'danger')
            return redirect(url_for('ContentManagmentSystem:login'))

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

        try:
            new_user = User(email, password, access_level=0)
            db.session.add(new_user)
            db.session.commit()
            flash(
                'Your account has been created successfuly! '
                'Now you can login with the form below:',
                'success'
            )
            return redirect(url_for('ContentManagmentSystem:login'))
        except ValidationError as e:
            flash(e.message, 'danger')
            return self._template('register')
        except IntegrityError:
            db.session.rollback()

        already_a_user = User.query.filter_by(email=email).count()

        if already_a_user:
            flash(
                'This email is already used for an account. '
                'If you do not remember your password, please contact us.',
                'warning'
            )
        else:
            flash(
                'Something gone wrong when creating your account. '
                'If the problem reoccurs please contact us.',
                'danger'
            )

        return self._template('register')

    @login_required
    def my_datasets(self):
        return self._template('datasets')

    def logout(self):
        logout_user()
        return redirect(request.url_root)
