import json
from view_testing import ViewTest
from models import Protein
from models import Gene
from models import Site
from models import Kinase
from models import Mutation
from models import CancerMutation
from models import Cancer
from database import db


def create_test_protein():

    g_x = Gene(name='Gene X')
    p = Protein(refseq='NM_0007', gene=g_x, sequence='TRAN')
    return p


class TestNetworkView(ViewTest):

    def test_show(self):
        p = create_test_protein()
        db.session.add(p)

        response = self.client.get('/network/show/NM_0007')
        assert response.status_code == 200

    def test_empty_representation(self):
        # test case 0: does empty network returns correct JSON response?
        p = create_test_protein()
        db.session.add(p)

        response = self.client.get('/network/representation/NM_0007')
        assert response.status_code == 200
        representation = json.loads(response.data.decode())
        assert representation
        assert representation['kinases'] == []
        assert representation['protein']['name'] == 'Gene X'

    def test_representation(self):
        p = create_test_protein()

        name = 'Kinase Y'
        refseq = 'NM_0009'

        # having a mutation (from TCGA here as this is the default mutations'
        # subset) is right now required if we want to have a kinase returned
        # in network representation, although this may not be desired; see #72
        mutation = Mutation(
            position=1,
            alt='T',
            meta_cancer=[CancerMutation(
                cancer=Cancer(name='Ovarian', code='OV')
            )]
        )

        interactor = Kinase(
            name=name,
            protein=Protein(
                refseq=refseq,
                gene=Gene(name='Gene of ' + name),
                mutations=[mutation]
            )
        )
        s = Site(
            position=1,
            type='phosphorylation',
            residue='T',
            kinases=[interactor]
        )
        p.sites = [s]
        db.session.add(p)

        response = self.client.get('/network/representation/NM_0007')
        assert response.status_code == 200
        representation = json.loads(response.data.decode())
        assert ['Kinase Y'] == representation['protein']['kinases']
        assert 'Kinase Y' == representation['kinases'][0]['name']

    def test_divide_muts_by_sites(self):
        from views.network import divide_muts_by_sites

        # check if null case works
        divide_muts_by_sites([], [])

        # one site
        s_1 = Site(position=1)
        muts_by_sites = divide_muts_by_sites([], [s_1])
        assert muts_by_sites[s_1] == []

        # full test
        s_2 = Site(position=10)
        s_3 = Site(position=20)

        muts_by_pos = {
            pos: [Mutation(position=pos)]
            for pos in (1, 2, 8, 14, 16, 30)
        }

        muts_by_pos[16].append(Mutation(position=16))

        def get_muts_from_pos(*positions):
            lists = [
                muts_by_pos[p]
                for p in positions
            ]
            return [
                mut
                for mut_list in lists
                for mut in mut_list
            ]

        muts_by_sites = divide_muts_by_sites(
            [
                mut
                for muts_on_pos_x in muts_by_pos.values()
                for mut in muts_on_pos_x
            ],
            [s_1, s_2, s_3]
        )

        assert muts_by_sites[s_1] == get_muts_from_pos(1, 2, 8)
        assert muts_by_sites[s_2] == get_muts_from_pos(8, 14, 16)
        assert muts_by_sites[s_3] == get_muts_from_pos(14, 16)
