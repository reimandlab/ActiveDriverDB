from getpass import getpass
from warnings import warn

from sqlalchemy.exc import IntegrityError

from exceptions import ValidationError
from database import db
from helpers.parsers import parse_text_file
from imports.importer import CMSImporter
from models.cms import BadWord, Page, User


class IndexPage(CMSImporter):

    requires = []

    def load(self):
        if Page.query.filter_by(address='index').first():
            warn('Index page already exists, skipping...')
            return
        content = """
        <ul>
            <li><a href="/search/proteins">search for a protein</a>
            <li><a href="/search/mutations">search for mutations</a>
        </ul>
        """
        main_page = Page(
            content=content,
            title='ActiveDriverDB',
            address='index'
        )
        print('Index page created')
        return [main_page]


class BadWordsImporter(CMSImporter):

    requires = []

    def load(self, path='data/bad-words.txt'):

        list_of_profanities = []
        parse_text_file(
            path,
            list_of_profanities.append,
            file_opener=lambda name: open(name, encoding='utf-8')
        )
        bad_words = [
            BadWord(word=word)
            for word in list_of_profanities
        ]
        return bad_words


class RootAccount(CMSImporter):

    requires = []

    def load(self):
        print('Creating root user account')

        correct = False

        while not correct:
            try:
                email = input('Please type root email: ')
                password = getpass(
                    'Please type root password (you will not see characters '
                    'you type due to security reasons): '
                )
                root = User(email, password, access_level=10)
                root.is_verified = True
                correct = True
            except ValidationError as e:
                print('Root credentials are incorrect: ', e.message)
                print('Please, try to use something different or more secure:')
            except IntegrityError:
                db.session.rollback()
                print(
                    'IntegrityError: either a user with this email already '
                    'exists or there is a serious problem with the database. '
                    'Try to use a different email address'
                )

        db.session.add(root)
        db.session.commit()
        print('Root user with email', email, 'created')

        print('Root user account created')
