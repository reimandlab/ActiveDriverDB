from imports.protein_data import kinase_mappings as load_kinase_mappings
from database_testing import DatabaseTest
from miscellaneous import make_named_temp_file
from database import db
from models import Kinase, Protein, Gene


# head data/curated_kinase_IDs.txt
curated_kinases_list = """\
LCK	LCK
SRC	SRC
FYN	FYN
ABL	ABL1
CDK2	CDK2
CHK1	CHEK1
CDK1	CDK1
PDK-1	PDK1
"""


class TestImport(DatabaseTest):

    def test_mappings(self):

        genes = {}
        for i, gene_name in enumerate(['LCK', 'SRC', 'FYN', 'PDK', 'PDK1']):
            gene = Gene(name=gene_name, preferred_isoform=Protein(refseq='NM_000%s' % i))
            genes[gene_name] = gene

        db.session.add_all(genes.values())

        # create a single pre-defined kinase with wrongly assigned protein (PDK for PDK-1)
        pdk_1 = Kinase(name='PDK-1', protein=genes['PDK'].preferred_isoform)

        # a kinase without protein assigned
        fyn = Kinase(name='FYN')

        db.session.add_all([pdk_1, fyn])

        filename = make_named_temp_file(curated_kinases_list)

        with self.app.app_context():
            new_kinases = load_kinase_mappings(filename)

            # new kinases shall be created only for the 5 gene which are
            # already present in the database, but out of these 5 genes
            # only 4 occur in the curated list of kinase-gene mappings;
            # moreover two of these 4 kinases already exists (PDK-1, FYN)
            assert len(new_kinases) == 2

            db.session.add_all(new_kinases)

            # test protein assignment
            lck = Kinase.query.filter_by(name='LCK').one()

            cases = {
                # was the kinase created and a correct protein assigned?
                lck: 'LCK',
                # was the protein assigned to existing kinase
                fyn: 'FYN',
                # was the protein of PDK-1 re-assigned to PDK1?
                pdk_1: 'PDK1'
            }

            for kinase, gene_name in cases.items():
                assert kinase.protein == genes[gene_name].preferred_isoform
