import gzip
from argparse import Namespace

from imports.mutations import MutationImportManager
from database_testing import DatabaseTest
from models import Protein
from models import Cancer
from models import Gene
from models import Mutation
from models import MC3Mutation
from models import InheritedMutation, Disease
from models import ClinicalData
from models import Site, Kinase
from database import db
from miscellaneous import make_named_temp_file
from manage import ProteinRelated

muts_import_manager = MutationImportManager()


def create_test_models():
    protein = Protein(refseq='NM_0001', gene=Gene(name='SOMEGENE'), sequence='ABCD')
    mutation = Mutation(protein=protein, position=1, alt='E')
    protein.gene.preferred_isoform = protein

    MC3Mutation(mutation=mutation, cancer=Cancer(code='CAN'), samples='Some sample')
    InheritedMutation(mutation=mutation, clin_data=[ClinicalData(disease=Disease(name='Some disease'))])

    protein_kinase = Protein(refseq='NM_0002', gene=Gene(name='OTHERGENE'), sequence='ABCD')
    kinase = Kinase(name='Kinase name', protein=protein_kinase)
    site = Site(protein=protein, position=1, residue='A', kinases={kinase}, pmid={1, 2}, type={'glycosylation'})
    protein.sites = [site]

    return locals()


class TestExport(DatabaseTest):

    def test_mutations_export(self):

        mc3_filename = make_named_temp_file()
        clinvar_filename = make_named_temp_file()

        with self.app.app_context():
            test_models = create_test_models()
            db.session.add_all(test_models.values())

            protein = test_models['protein']

            muts_import_manager.perform(
                'export', [protein], ['mc3'], {'mc3': mc3_filename}
            )
            muts_import_manager.perform(
                'export', [protein], ['clinvar'], {'clinvar': clinvar_filename}
            )

        with gzip.open(mc3_filename) as f:
            assert f.readlines() == [
                b'gene\tisoform\tposition\twt_residue\tmut_residue\tcancer_type\n',
                b'SOMEGENE\tNM_0001\t1\tA\tE\tCAN'
            ]

        with gzip.open(clinvar_filename) as f:
            assert f.readlines() == [
                b'gene\tisoform\tposition\twt_residue\tmut_residue\tdisease\n',
                b'SOMEGENE\tNM_0001\t1\tA\tE\tSome disease'
            ]

    def test_network_export(self, do_export=None):

        filename = make_named_temp_file()

        with self.app.app_context():
            test_models = create_test_models()
            db.session.add_all(test_models.values())

            if do_export:
                do_export(filename)
            else:
                namespace = Namespace(exporters=['site_specific_network_of_kinases_and_targets'], paths=[filename])
                ProteinRelated.export(namespace)

        with open(filename) as f:
            assert f.readlines() == [
                'kinase symbol\ttarget symbol\tkinase refseq\ttarget refseq\ttarget sequence position\ttarget amino acid\n',
                'Kinase name\tSOMEGENE\tNM_0002\tNM_0001\t1\tA\n'
            ]

    def test_ptm_mutations(self):

        filename = make_named_temp_file()

        with self.app.app_context():
            test_models = create_test_models()
            db.session.add_all(test_models.values())

            namespace = Namespace(exporters=['mc3_muts_affecting_ptm_sites'], paths=[filename])
            ProteinRelated.export(namespace)

        with open(filename) as f:
            assert f.readlines() == [
                'gene	refseq	mutation position	mutation alt	mutation summary	site position	site residue\n',
                'SOMEGENE\tNM_0001\t1\tE\tCAN\t1\tA\n'
            ]

    def test_sites_export(self):

        filename = make_named_temp_file()

        with self.app.app_context():
            test_models = create_test_models()
            db.session.add_all(test_models.values())

            namespace = Namespace(exporters=['sites_ac'], paths=[filename])
            ProteinRelated.export(namespace)

        with open(filename) as f:
            assert f.readlines() == [
                'gene\tposition\tresidue\ttype\tkinase\tpmid\n',
                'SOMEGENE\t1\tA\tglycosylation\tKinase name\t1,2\n'
            ]
