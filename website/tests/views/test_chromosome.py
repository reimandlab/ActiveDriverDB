from view_testing import ViewTest
from models import Mutation, Cancer, MC3Mutation, ExomeSequencingMutation
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
        from genomic_mappings import make_snv_key
        from genomic_mappings import encode_csv

        muts = [(13, 14370), (15, 14376)]

        for aa_pos, dna_pos in muts:
            # (those are fake data)
            csv = encode_csv('+', 'A', 'V', aa_pos * 3, 'EX1', p.id, True)

            # map the first genomic mutation from VCF_FILE_CONTENT
            # to some (mocked) protein mutation
            bdb[make_snv_key('20', dna_pos, 'G', 'A')].add(csv)

        query_url = '/chromosome/mutation/{chrom}/{pos}/{ref}/{alt}'

        # query as a novel mutation
        response = self.client.get(query_url.format(chrom='chr20', pos=14370, ref='G', alt='A'))

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

        # well let's look on a known mutation:
        m = Mutation(position=15, protein=p, alt='V')
        mc3 = MC3Mutation(mutation=m, cancer=Cancer(name='BRCA'), count=1)
        esp = ExomeSequencingMutation(mutation=m, maf_all=0.02, maf_aa=0.02)

        db.session.add_all([m, mc3, esp])
        db.session.commit()

        mutation_a15v_query = query_url.format(chrom='chr20', pos=14376, ref='G', alt='A')
        response = self.client.get(mutation_a15v_query)

        metadata = {
            'MC3': {'MC3metadata': [{'Cancer': 'BRCA', 'Value': 1}]},
            'ESP6500': {'MAF': 0.02, 'MAF AA': 0.02, 'MAF EA': None}
        }

        assert response.json[0]['in_datasets'] == metadata

        expected_values = {'MC3': 1, 'ESP6500': 0.02}

        # if user does not want to download data for all datasets he may use:
        for source, meta in metadata.items():
            response = self.client.get(mutation_a15v_query + '?filters=Mutation.sources:in:' + source)
            json = response.json[0]
            assert json['in_datasets'] == {source: meta}
            assert json['value'] == expected_values[source]
