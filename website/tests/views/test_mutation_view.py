from view_testing import ViewTest
from models import Mutation, MC3Mutation, source_manager
from models import Protein
from models import Gene
from database import db


class TestMutationView(ViewTest):

    def test_show(self):

        p = Protein(refseq='NM_000123', sequence='TRAN', gene=Gene(name='TP53'))
        mutation = Mutation(protein=p, position=2, alt='K')

        db.session.add(mutation)

        response = self.client.get('/mutation/show/NM_000123/2/K')

        assert response.status_code == 200
        assert b'TP53' in response.data
        assert b'NM_000123' in response.data

    def test_prepare_dataset(self):
        from views.mutation import prepare_datasets

        p = Protein(refseq='NM_000123', sequence='TRAN', gene=Gene(name='TP53'))
        mutation = Mutation(protein=p, position=2, alt='K')
        details = MC3Mutation(mutation=mutation, count=2)

        db.session.add(mutation)

        datasets, user_datasets = prepare_datasets(mutation)

        expected_datasets = [
            {
                'filter': 'Mutation.sources:in:' + source.name,
                'name': source.display_name,
                'mutation_present': False
            }
            if source is not MC3Mutation else
            {
                'filter': 'Mutation.sources:in:' + MC3Mutation.name,
                'name': MC3Mutation.display_name,
                'mutation_present': [details]
            }
            for source in source_manager.confirmed
        ]

        assert datasets == expected_datasets
        assert not user_datasets
