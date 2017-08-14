from contextlib import contextmanager
from tests.database_testing import DatabaseTest


class Flash:
    def __init__(self, content=None, category=None):
        self.content = content
        self.category = category

    def __repr__(self):
        return '<Flash %s: %s>' % (self.category, self.content)


class ViewTest(DatabaseTest):

    def view_module(self):
        """Required to be defined in subclasses in order to use flash assertions"""
        return None

    def setUp(self):
        super().setUp()
        self.module = self.view_module()

    @contextmanager
    def collect_flashes(self):
        flashes = []

        original_flash = self.module.flash

        def flash_collector(*args, **kwargs):
            collected_flash = Flash(*args, **kwargs)
            flashes.append(collected_flash)
            original_flash(*args, **kwargs)

        self.module.flash = flash_collector

        yield flashes

        self.module.flash = original_flash

    @contextmanager
    def assert_flashes(self, *args, **kwargs):
        """(kw)args are: content and category of expected flashes"""
        with self.collect_flashes() as flashes:
            yield
            assert self.assert_flashed(flashes, *args, **kwargs)

    @staticmethod
    def assert_flashed(flashes, content=None, category=None):
        for flash in flashes:
            if (content is None or flash.content == content) and (category is None or flash.category == category):
                return True
        raise AssertionError('No flash: %s, %s. Recent flashes: %s.' % (content, category, flashes))
