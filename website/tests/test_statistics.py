from pandas import DataFrame
from pytest import raises

from imports.protein_data import precompute_ptm_mutations
from database_testing import DatabaseTest
from database import db
import models
from models import (
    Protein, Site, Mutation, MIMPMutation, InheritedMutation, MC3Mutation, The1000GenomesMutation,
    SiteType, ClinicalData, ExomeSequencingMutation,
)


class StatisticsTest(DatabaseTest):

    def exposed_stats(self, limit_to):
        from stats import Statistics
        s = Statistics()
        s.calc_all(limit_to=limit_to)
        return s.get_all()

    def test_simple_models(self):

        model_stats = {
            'pathways': models.Pathway,
            'proteins': models.Protein,
            'genes': models.Gene,
            'kinases': models.Kinase,
            'kinase_groups': models.KinaseGroup,
            'sites': models.Site,
            'cancer': models.Cancer
        }

        for name, model in model_stats.items():
            model_objects = [model() for _ in range(10)]
            db.session.add_all(model_objects)

        stats = self.exposed_stats(limit_to='|'.join(model_stats))

        for name, model in model_stats.items():
            assert stats[name] == 10

    def test_mutations_count(self):

        mutation_counts = {
            models.MIMPMutation: 100,
            models.The1000GenomesMutation: 3,
            models.MC3Mutation: 5,
            models.ExomeSequencingMutation: 2,
            models.InheritedMutation: 4
        }

        mutation_models = {
            model.name: model
            for model in mutation_counts.keys()
        }

        for model, count in mutation_counts.items():
            for _ in range(count):
                m = models.Mutation()
                metadata = model(mutation=m)
                db.session.add(metadata)
            db.session.commit()

        stats = self.exposed_stats(limit_to='mutations')

        def get_var_name(model_name):
            return model_name.replace('1', 'T')

        for name, model in mutation_models.items():
            assert stats['muts'][get_var_name(name)] == mutation_counts[model]

        assert stats['muts']['all'] == sum(mutation_counts.values())

        # confirmed are all without mimp
        assert stats['muts']['all_confirmed'] == 3 + 5 + 2 + 4

    def test_from_many_sources(self):

        # create one mutation which is present in multiple sources
        m = models.Mutation()
        metadata_1 = models.InheritedMutation(mutation=m)
        metadata_2 = models.MC3Mutation(mutation=m)
        db.session.add_all([metadata_1, metadata_2])

        from stats import Statistics
        statistics = Statistics()

        in_many_sources = statistics.from_more_than_one_source()

        assert in_many_sources == 1

    def test_sites_stats(self):

        from models import Site, SiteType

        site_counts = {
            'glycosylation': 100,
            'N-glycosylation': 10,
            'O-glycosylation': 5,
            'phosphorylation': 25
        }

        for site_type, count in site_counts.items():
            site_type = SiteType(name=site_type)
            for _ in range(count):
                site = Site(types={site_type})
                db.session.add(site)

        from stats import Statistics
        statistics = Statistics()
        statistics.calc_all(limit_to='(glycosylation|sites)')
        statistics = statistics.get_all()

        assert statistics['glycosylations_with_subtype'] == 15
        assert statistics['glycosylations_without_subtype_ratio'] == 100 / 115

        assert statistics['sites'] == sum(site_counts.values())

    def test_interactions(self):

        from models import Protein, Site, Kinase, KinaseGroup

        p1 = Protein(
            sites=[
                Site(),
                Site(kinases={Kinase()}, kinase_groups={KinaseGroup()})
            ]
        )
        db.session.add(p1)
        p2 = Protein(
            sites=[Site(kinases={Kinase()})]
        )
        db.session.add(p2)

        u_all_interactions = 0
        u_kinases_covered = set()
        u_kinase_groups_covered = set()
        u_proteins_covered = set()
        for protein in models.Protein.query.all():
            for site in protein.sites:
                kinases = site.kinases
                kinase_groups = site.kinase_groups
                u_all_interactions += len(kinases) + len(kinase_groups)
                u_kinases_covered.update(kinases)
                u_kinase_groups_covered.update(kinase_groups)

                if kinases or kinase_groups:
                    u_proteins_covered.add(protein)

        from stats import Statistics
        statistics = Statistics()
        all_interactions = statistics.interactions()
        kinases_covered = statistics.kinases_covered()
        kinase_groups_covered = statistics.kinase_groups_covered()
        proteins_covered = statistics.proteins_covered()

        assert all_interactions == u_all_interactions
        assert kinases_covered == len(u_kinases_covered)
        assert kinase_groups_covered == len(u_kinase_groups_covered)
        assert proteins_covered == len(u_proteins_covered)

    def test_table_generation(self):
        from stats.table import generate_source_specific_summary_table

        # TODO only_primary?

        table = generate_source_specific_summary_table()
        assert table

    def test_table_source_specific_mutated_sites(self):
        from stats.table import source_specific_mutated_sites

        protein = Protein(refseq='NM_0001', sequence='MSSSGTPDLPVLLTDLKIQYTKIFINNEWHDSVSGK')
        db.session.add(protein)

        phosphorylation = SiteType(name='phosphorylation')
        hydroxylation = SiteType(name='hydroxylation')

        site_2 = Site(position=2, residue='S', protein=protein, types={phosphorylation})
        site_10 = Site(position=10, residue='P', protein=protein, types={hydroxylation})
        db.session.add_all([site_2, site_10])

        mutations = {
            # affecting phosphorylation site 2S
            1: Mutation(position=1, alt='X', protein=protein),
            2: Mutation(position=2, alt='X', protein=protein),
            3: Mutation(position=3, alt='X', protein=protein),
            # affecting hydroxylation site 10P
            10: Mutation(position=10, alt='X', protein=protein),
            11: Mutation(position=11, alt='X', protein=protein),
            12: Mutation(position=12, alt='X', protein=protein),
            # NOT affecting any of the sites
            30: Mutation(position=30, alt='X', protein=protein),
            31: Mutation(position=31, alt='X', protein=protein),
        }

        metadata = [
            # affecting phosphorylation site 2S
            MC3Mutation(
                mutation=mutations[1],
                # the number of patients should NOT count
                count=2
            ),
            InheritedMutation(
                mutation=mutations[1],
                # the number of disease associations does NOT count
                clin_data=[ClinicalData(), ClinicalData()]
            ),
            # NOT affecting site 2S (non-confirmed mutation)
            MIMPMutation(mutation=mutations[2]),
            MIMPMutation(mutation=mutations[3]),
            # affecting hydroxylation site 10P
            InheritedMutation(mutation=mutations[10], clin_data=[ClinicalData()]),
            The1000GenomesMutation(mutation=mutations[11]),
            ExomeSequencingMutation(mutation=mutations[12]),
            # NOT affecting any of the sites
            MC3Mutation(mutation=mutations[30], count=3),
            MC3Mutation(mutation=mutations[31], count=1),
        ]
        db.session.add_all(metadata)
        db.session.commit()

        # raises if not mutations were precomputed
        with raises(ValueError):
            source_specific_mutated_sites()

        precompute_ptm_mutations.load()
        db.session.commit()

        sites_affected = DataFrame(source_specific_mutated_sites())

        # two site types + any type
        assert len(sites_affected.index) == 3
        sites_affected.index = [
            site_type.name or 'any type'
            for site_type in sites_affected.index
        ]

        assert set(sites_affected.index) == {'hydroxylation', 'phosphorylation', 'any type'}

        # affecting phosphorylation site 2S
        assert sites_affected.loc['phosphorylation', 'MC3'] == 1
        assert sites_affected.loc['phosphorylation', 'ClinVar'] == 1
        assert sites_affected.loc['phosphorylation', '1KGenomes'] == 0
        assert sites_affected.loc['phosphorylation', 'ESP6500'] == 0
        assert sites_affected.loc['phosphorylation', 'Any mutation'] == 1

        # affecting hydroxylation site 10P
        assert sites_affected.loc['hydroxylation', 'MC3'] == 0
        assert sites_affected.loc['hydroxylation', 'ClinVar'] == 1
        assert sites_affected.loc['hydroxylation', '1KGenomes'] == 1
        assert sites_affected.loc['hydroxylation', 'ESP6500'] == 1
        assert sites_affected.loc['hydroxylation', 'Any mutation'] == 1

        # any site type
        assert sites_affected.loc['any type', 'MC3'] == 1
        assert sites_affected.loc['any type', 'ClinVar'] == 2
        assert sites_affected.loc['any type', '1KGenomes'] == 1
        assert sites_affected.loc['any type', 'ESP6500'] == 1
        assert sites_affected.loc['any type', 'Any mutation'] == 2
