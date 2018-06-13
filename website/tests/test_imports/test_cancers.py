from imports.protein_data import cancers as load_cancers
from database_testing import DatabaseTest
from miscellaneous import make_named_temp_file
from database import db


cancers_list = """\
BLCA	Bladder Urothelial Carcinoma	yellow
BRCA	Breast invasive carcinoma	darkolivegreen2\
"""


class TestImport(DatabaseTest):

    def test_cancer(self):

        filename = make_named_temp_file(cancers_list)

        with self.app.app_context():
            cancers = load_cancers(path=filename)

        # two cancers should be returned
        assert len(cancers) == 2

        cancer = cancers[0]

        assert cancer.name == 'Bladder Urothelial Carcinoma'
        assert cancer.code == 'BLCA'

        db.session.add_all(cancers)
        assert True
