import gzip
from imports.mutations import MutationImportManager
from database_testing import DatabaseTest
from models import Protein
from models import Cancer
from models import Gene
from models import Mutation
from models import MC3Mutation
from models import InheritedMutation
from models import ClinicalData
from database import db
from miscellaneous import make_named_temp_file

muts_import_manager = MutationImportManager()


class TestExport(DatabaseTest):

    def test_mutations_export(self):

        mc3_filename = make_named_temp_file()
        clinvar_filename = make_named_temp_file()

        with self.app.app_context():

            protein = Protein(refseq='NM_0001', gene=Gene(name='SOMEGENE'), sequence='ABCD')
            mutation = Mutation(protein=protein, position=1, alt='E')

            MC3Mutation(mutation=mutation, cancer=Cancer(code='CAN'), samples='Some sample')
            InheritedMutation(mutation=mutation, clin_data=[ClinicalData(disease_name='Some disease')])

            db.session.add(mutation)

            muts_import_manager.perform(
                'export', [protein], ['mc3'], {'mc3': mc3_filename}
            )
            muts_import_manager.perform(
                'export', [protein], ['clinvar'], {'clinvar': clinvar_filename}
            )

        with gzip.open(mc3_filename) as f:
            assert f.readlines() == [
                b'gene\tisoform\tposition\twt_residue\tmut_residue\tcancer_type\tsample_id\n',
                b'SOMEGENE\tNM_0001\t1\tA\tE\tCAN\tSome sample'
            ]

        with gzip.open(clinvar_filename) as f:
            assert f.readlines() == [
                b'gene\tisoform\tposition\twt_residue\tmut_residue\tdisease\n',
                b'SOMEGENE\tNM_0001\t1\tA\tE\tSome disease'
            ]
