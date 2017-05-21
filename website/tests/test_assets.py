import assets
from database_testing import DatabaseTest
from os import makedirs, remove


class TestDependencies(DatabaseTest):
    resources = {
        'dependency': assets.CSSResource(
            'http://some.de/pendency/it/is.ok',
        ),
        'dependency_with_integrity': assets.JSResource(
            'http://some.de/pendency/it/is.ok',
            'sha256-somehashcode'
        )
    }

    def test_dependency_manager(self):
        dm = assets.DependencyManager(self)
        dm.third_party = self.resources

        assert dm.get_dependency('dependency_with_integrity') == (
            '<script src="http://some.de/pendency/it/is.ok" '
            'integrity="sha256-somehashcode" crossorigin="anonymous"></script>'
        )

        assert dm.get_dependency('dependency') == '<link rel="stylesheet" href="http://some.de/pendency/it/is.ok">'

        self.USE_CONTENT_DELIVERY_NETWORK = False

        dm = assets.DependencyManager(self)
        dm.third_party = self.resources

        file_path = 'static/thirdparty/pendency/it/is.ok'
        makedirs('static/thirdparty/pendency/it/', exist_ok=True)
        open(file_path, 'w').close()

        assert dm.get_dependency('dependency') == '<link rel="stylesheet" href="/static/thirdparty/pendency/it/is.ok">'

        remove(file_path)
