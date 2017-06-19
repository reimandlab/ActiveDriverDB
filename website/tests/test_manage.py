from argparse import Namespace

from database_testing import DatabaseTest
from flask import current_app

import manage
from database import db
from models import User, Gene, Cancer, Page
from tests.miscellaneous import make_named_temp_file, use_fixture


class ManageTest(DatabaseTest):

    LOAD_STATS = False

    def test_automigrate(self):
        """Simple blackbox test for automigrate."""
        args = Namespace(databases=('bio', 'cms'))
        with current_app.app_context():
            result = manage.automigrate(args, current_app)
        assert result

    def test_parser_creation(self):
        parser = manage.create_parser()
        assert parser

    def run_command(self, commands, allow_early_exit=False):
        parser = manage.create_parser()
        try:
            parsed_args = parser.parse_args(commands.split(' '))
            manage.run_manage(parsed_args, my_app=self.app)
        except SystemExit:
            if not allow_early_exit:
                raise
        msg, errors = self.capsys.readouterr()
        return msg, errors

    def test_help(self):

        def get_help(commands):
            help_msg, errors = self.run_command(commands, allow_early_exit=True)
            assert not errors
            return help_msg

        help_message = get_help('-h')
        choices = 'load,remove,export,update,migrate'.split(',')
        assert all(choice in help_message for choice in choices)

        # test load help
        help_message = get_help('load -h')
        choices = 'cms,mutations,protein_related,snv_to_csv_mapping,all'.split(',')
        assert all(choice in help_message for choice in choices)

        # test load mutations help
        help_message = get_help('load mutations -h')
        assert '--sources' in help_message
        assert '--only_primary_isoforms' not in help_message   # this is export parameter should not be there

        # test export help
        help_message = get_help('export mutations -h')
        assert '--sources' in help_message
        assert '--only_primary_isoforms' in help_message

        help_message = get_help('export protein_related -h')
        assert '--only_primary_isoforms' not in help_message   # this is export mutations parameter should not be there
        assert '--paths' in help_message
        assert '--exporters' in help_message

        # test remove help
        help_message = get_help('remove -h')
        choices = 'cms,mutations,protein_related,snv_to_csv_mapping'.split(',')
        assert all(choice in help_message for choice in choices)

        help_message = get_help('remove protein_related -h')
        some_of_models = 'Cancer Protein Site ProteinReferences Gene Pathway'.split(' ')
        assert '--models' in help_message
        for model_name in some_of_models:
            assert model_name in help_message
        assert 'Page' not in help_message   # this model should not be possible to remove from 'protein_related'

        # test migrate help
        help_message = get_help('migrate -h')
        assert 'bio' in help_message
        assert 'cms' in help_message

    def test_export_paths(self):

        name_1 = make_named_temp_file()
        name_2 = make_named_temp_file()

        # user gave too many paths
        msg, error = self.run_command('export protein_related -e sites_ac --paths %s %s' % (name_1, name_2))
        assert 'Export paths should be given for every exported file, no less, no more.' in msg

        # user gave good number of paths
        msg, error = self.run_command('export protein_related -e sites_ac --paths %s' % name_1)
        assert 'Export paths should be given for every exported file, no less, no more.' not in msg
        assert ('Exported sites_ac to %s' % name_1) in msg

    def test_export(self):

        def do_export(filename):
            command = 'export protein_related -e site_specific_network_of_kinases_and_targets --paths %s' % filename
            msg, error = self.run_command(command)
            assert 'Exported site_specific_network_of_kinases_and_targets to %s' % filename in msg

        from tests.test_imports.test_export import TestExport
        TestExport.test_network_export(self, do_export)

    def test_cms(self):
        email = 'root-email@gmail.com'
        self.monkeypatch.setitem(__builtins__, 'input', lambda prompt: email)
        self.monkeypatch.setattr(manage, 'getpass', lambda prompt: 'my-sEcure-passw0rd')
        msg, error = self.run_command('load cms')
        assert User.query.filter_by(email=email).one()
        assert 'Root user account created' in msg

    def test_remove(self):

        with current_app.app_context():
            assert len(Gene.query.all()) == 0
            assert len(Cancer.query.all()) == 0

            g = Gene(name='test_gene')
            c = Cancer(name='test_cancer')
            db.session.add_all([g, c])
            db.session.commit()

            assert Gene.query.one()
            assert Cancer.query.one()

            self.run_command('remove protein_related --model Gene')

            assert len(Gene.query.all()) == 0
            assert len(Cancer.query.all()) == 1

    def test_drop_all(self):
        with current_app.app_context():
            example_models = [Gene, Cancer, Page]
            assert all(len(model.query.all()) == 0 for model in example_models)

            db.session.add_all([model() for model in example_models])
            db.session.commit()

            assert all(len(model.query.all()) == 1 for model in example_models)

            self.run_command('remove all')

            assert all(len(model.query.all()) == 0 for model in example_models)

    @use_fixture
    def capsys(self, capsys):
        self.capsys = capsys

    @use_fixture
    def monkeypatch(self, monkeypatch):
        self.monkeypatch = monkeypatch
