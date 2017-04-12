from view_testing import ViewTest
from models import Mutation
from models import Protein
from models import Site
from models import Gene
from database import db


class TestChromosomeView(ViewTest):

    def test_mutation(self):

        s = Site(position=13, type='methylation')
        p = Protein(refseq='NM_007', id=1, sites=[s], sequence='A'*15, gene=Gene(name='SomeGene'))

        db.session.add(p)

        from database import bdb
        from database import make_snv_key
        from database import encode_csv

        # (those are fake data)
        csv = encode_csv('+', 'A', 'V', 13 * 3, 'EX1', p.id, True)

        # map the first genomic mutation from VCF_FILE_CONTENT
        # to some (mocked) protein mutation
        bdb[make_snv_key('20', 14370, 'G', 'A')].add(csv)

        query_url = '/chromosome/mutation/{chrom}/{pos}/{ref}/{alt}'.format(
            chrom='chr20',
            pos=14370,
            ref='G',
            alt='A'
        )

        response = self.client.get(query_url)

        assert response.status_code == 200
        assert response.json == [
            {
                'alt': 'V',
                'gene': 'SomeGene',
                'in_datasets': {},
                'pos': 13,
                'ptm_impact': 'direct',
                'cnt_ptm': 1,
                'closest_sites': ['13 A'],
                'protein': 'NM_007',
                'sites': [
                    {'kinases': [], 'position': 13, 'residue': 'A', 'kinase_groups': [], 'type': 'methylation'}
                ],
                'ref': 'A'
             }
        ]
