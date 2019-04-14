import gzip
from argparse import Namespace

from imports.mutations import MutationImportManager
from database_testing import DatabaseTest
from models import Protein, SiteType
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

    MC3Mutation(mutation=mutation, cancer=Cancer(code='CAN'), samples='Sample A,Sample B', count=2)
    InheritedMutation(mutation=mutation, clin_data=[
        ClinicalData(disease=Disease(name='Some disease'), sig_code=5),
        ClinicalData(disease=Disease(name='Other disease'), sig_code=2)
    ])

    protein_kinase = Protein(refseq='NM_0002', gene=Gene(name='OTHERGENE'), sequence='ABCD')
    kinase = Kinase(name='Kinase name', protein=protein_kinase)
    site = Site(
        protein=protein, position=1, residue='A',
        kinases={kinase}, pmid={1, 2}, types={SiteType(name='glycosylation')}
    )
    protein.sites = [site]

    return locals()


class TestExport(DatabaseTest):

    def test_mutations_export(self):

        cases = (
            (
                'mc3',
                {},
                [
                    b'gene\tisoform\tposition\twt_residue\tmut_residue\tcancer_type\tcount\n',
                    b'SOMEGENE\tNM_0001\t1\tA\tE\tCAN\t2'
                ]
            ),
            (
                'mc3',
                {'export_samples': True},
                [
                    b'gene\tisoform\tposition\twt_residue\tmut_residue\tcancer_type\tsample_id\n',
                    b'SOMEGENE\tNM_0001\t1\tA\tE\tCAN\tSample A\n',
                    b'SOMEGENE\tNM_0001\t1\tA\tE\tCAN\tSample B'
                ]
            ),
            (
                'clinvar',
                {},
                [
                    b'gene\tisoform\tposition\twt_residue\tmut_residue\tdisease\tsignificance\n',
                    b'SOMEGENE\tNM_0001\t1\tA\tE\tSome disease\tPathogenic\n',
                    b'SOMEGENE\tNM_0001\t1\tA\tE\tOther disease\tBenign'
                ]
            )
        )

        with self.app.app_context():
            test_models = create_test_models()
            db.session.add_all(test_models.values())

            protein = test_models['protein']

            for source, kwargs, expected_lines in cases:

                filename = make_named_temp_file()

                muts_import_manager.perform(
                    'export', [protein], [source], paths={source: filename}, **kwargs
                )

                with gzip.open(filename) as f:
                    assert f.readlines() == expected_lines

    def test_network_export(self, do_export=None):

        filename = make_named_temp_file()

        with self.app.app_context():
            test_models = create_test_models()
            db.session.add_all(test_models.values())

            if do_export:
                do_export(filename)
            else:
                namespace = Namespace(exporters=['site_specific_network_of_kinases_and_targets'], paths=[filename])
                ProteinRelated().export(namespace)

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
            ProteinRelated().export(namespace)

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
            ProteinRelated().export(namespace)

        with open(filename) as f:
            assert f.readlines() == [
                'gene\tposition\tresidue\ttype\tkinase\tpmid\n',
                'SOMEGENE\t1\tA\tglycosylation\tKinase name\t1,2\n'
            ]

    def test_ptm_muts_of_gene(self):

        filename = make_named_temp_file()

        with self.app.app_context():
            from models import clear_cache
            clear_cache()

            test_models = create_test_models()
            db.session.add_all(test_models.values())

            from exports.protein_data import ptm_muts_of_gene
            ptm_muts_of_gene(
                path_template=filename, mutation_source='mc3',
                gene='SOMEGENE', site_type='glycosylation', export_samples=True
            )

        with open(filename) as f:
            assert f.readlines() == [
                'gene\tisoform\tposition\twt_residue\tmut_residue\tcancer_type\tsample_id\n',
                'SOMEGENE\tNM_0001\t1\tA\tE\tCAN\tSample A\n',
                'SOMEGENE\tNM_0001\t1\tA\tE\tCAN\tSample B\n'
            ]
