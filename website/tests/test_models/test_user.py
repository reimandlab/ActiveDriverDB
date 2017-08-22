from database import db
from .model_testing import ModelTest
from models import User
import pytest
from sqlalchemy.exc import IntegrityError
from exceptions import ValidationError


class DatasetTest(ModelTest):

    def test_init(self):

        user = User('user@domain', 'password')

        assert user

        # check privileges
        assert not user.is_admin
        super_user = User('admin@domain', 'password', access_level=10)
        assert super_user.is_admin

        db.session.add(user)
        db.session.commit()

        # do not allow to create two users with the same email
        with pytest.raises(IntegrityError):
            other_user = User('user@domain', 'password')
            db.session.add(other_user)
            db.session.commit()

        wrong_mails = [
            'not_an_email',
            'wrong@e..mail',
            'name@' + ''.join([str(x) for x in range(300)]),
            '@lack_of_local_address'
            'lack_of_domain@'
        ]

        for wrong_mail in wrong_mails:
            print(wrong_mail)
            with pytest.raises(ValidationError):
                User(wrong_mail, 'password')

        weak_passwords = [
            'pass',
            'aaaaaaa',
            'p',
            '1'
        ]

        for weak_pass in weak_passwords:
            print(weak_pass)
            with pytest.raises(ValidationError):
                User('correct@mail', weak_pass)
