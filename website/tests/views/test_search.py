from io import BytesIO

from view_testing import ViewTest

from database import db
from models import Gene
from models import Protein
from models import UsersMutationsDataset
from models import Site
from models import Mutation


# base on example from specification in version 4.3:
# http://samtools.github.io/hts-specs/VCFv4.3.pdf
VCF_FILE_CONTENT = b"""\
##fileformat=VCFv4.3
##fileDate=20090805
##source=myImputationProgramV3.1
##reference=file:///seq/references/1000GenomesPilot-NCBI36.fasta
##contig=<ID=20,length=62435964,assembly=B36,md5=f126cdf8a6e0c7f379d618ff66beb2da,species="Homo sapiens",taxonomy=x>
##phasing=partial
##INFO=<ID=NS,Number=1,Type=Integer,Description="Number of Samples With Data">
##INFO=<ID=DP,Number=1,Type=Integer,Description="Total Depth">
##INFO=<ID=AF,Number=A,Type=Float,Description="Allele Frequency">
##INFO=<ID=AA,Number=1,Type=String,Description="Ancestral Allele">
##INFO=<ID=DB,Number=0,Type=Flag,Description="dbSNP membership, build 129">
##INFO=<ID=H2,Number=0,Type=Flag,Description="HapMap2 membership">
##FILTER=<ID=q10,Description="Quality below 10">
##FILTER=<ID=s50,Description="Less than 50% of samples have data">
##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">
##FORMAT=<ID=GQ,Number=1,Type=Integer,Description="Genotype Quality">
##FORMAT=<ID=DP,Number=1,Type=Integer,Description="Read Depth">
##FORMAT=<ID=HQ,Number=2,Type=Integer,Description="Haplotype Quality">
#CHROM POS     ID        REF    ALT     QUAL FILTER INFO                              FORMAT      NA00001        NA00002        NA00003
20     14370   rs6054257 G      A       29   PASS   NS=3;DP=14;AF=0.5;DB;H2           GT:GQ:DP:HQ 0|0:48:1:51,51 1|0:48:8:51,51 1/1:43:5:.,.
20     17330   .         T      A       3    q10    NS=3;DP=11;AF=0.017               GT:GQ:DP:HQ 0|0:49:3:58,50 0|1:3:5:65,3   0/0:41:3
20     1110696 rs6040355 A      G,T     67   PASS   NS=2;DP=10;AF=0.333,0.667;AA=T;DB GT:GQ:DP:HQ 1|2:21:6:23,27 2|1:2:0:18,2   2/2:35:4
20     1230237 .         T      .       47   PASS   NS=3;DP=13;AA=T                   GT:GQ:DP:HQ 0|0:54:7:56,60 0|0:48:4:51,51 0/0:61:2
20     1234567 microsat1 GTC    G,GTCT  50   PASS   NS=3;DP=9;AA=G                    GT:GQ:DP    0/1:35:4       0/2:17:2       1/1:40:3\
"""


def mock_proteins_and_genes(count):
    for i in range(count):
        g = Gene(name='Gene_%s' % i)
        p = Protein(refseq='NM_000%s' % i, gene=g)
        g.preferred_isoform = p
        db.session.add(g)


class TestSearchView(ViewTest):

    def test_searchbar(self):
        mock_proteins_and_genes(15)

        response = self.client.get(
            'search/autocomplete_searchbar?q=%s' % 'Gene',
            follow_redirects=True
        )
        assert response.status_code == 200
        assert response.json['entries'][0]['name'].startswith('Gene')

    def test_search_proteins(self):
        from views.search import search_proteins

        # create 15 genes and proteins
        mock_proteins_and_genes(15)

        assert not search_proteins('TP53')

        results = search_proteins('Gene', 10)

        assert results
        assert len(results) == 10

        assert results[0].name.startswith('Gene')

        # should not be case sensitive
        results = search_proteins('gene', 1)
        assert results

        # the same for refseq search
        assert search_proteins('NM_0003', 1)
        assert search_proteins('nm_0003', 1)
        assert search_proteins('0003', 1)

        assert not search_proteins('9999', 1)

    def test_search_proteins_view(self):

        mock_proteins_and_genes(15)

        response = self.client.get(
            '/search/proteins?proteins=Gene_2',
            follow_redirects=True
        )

        assert response.status_code == 200
        assert b'Gene_2' in response.data
        assert b'NM_0002' in response.data

    def search_mutations(self, **data):
        return self.client.post(
            '/search/mutations',
            data=data
        )

    def test_search_mutations(self):

        s = Site(position=13, type='methylation')
        p = Protein(refseq='NM_007', id=7, sites=[s])

        m_in_site = Mutation(protein=p, position=13, alt='V')
        m_out_site = Mutation(protein=p, position=50, alt='K')

        db.session.add(p)

        # points to the same location as first record in VCF_FILE_CONTENT
        test_query = 'chr20 14370 G A'

        from database import bdb
        from database import make_snv_key
        from database import encode_csv

        # (those are fake data)
        csv = encode_csv('+', 'A', 'V', 13 * 3, 'EX1', p.id, True)

        # map the first genomic mutation from VCF_FILE_CONTENT
        # to some (mocked) protein mutation
        bdb[make_snv_key('20', 14370, 'G', 'A')].add(csv)

        #
        # basic test - is appropriate mutation in results?
        #
        response = self.search_mutations(mutations=test_query)

        assert response.status_code == 200

        # this mutation is exactly at a PTM site and should be included in results
        assert '<td>{0}</td>'.format(m_in_site.alt).encode() in response.data
        # this mutation lies outside of a PTM site - be default should be filtered out
        assert '<td>{0}</td>'.format(m_out_site.alt).encode() not in response.data

        #
        # count test - is mutation for this query annotated as shown twice?
        #
        response = self.search_mutations(
            mutations='{0}\n{0}'.format(test_query)
        )

        assert response.status_code == 200
        assert b'<td>2</td>' in response.data

        #
        # VCF file test
        #
        response = self.client.post(
            '/search/mutations',
            content_type='multipart/form-data',
            data={
                'vcf-file': (BytesIO(VCF_FILE_CONTENT), 'exemplar_vcf.vcf')
            }
        )

        assert response.status_code == 200
        assert b'NM_007' in response.data

    def test_autocomplete(self):
        g = Gene(name='BR')
        p = Protein(refseq='NM_007', gene=g, sequence='XXXXXV')
        mut = Mutation(protein=p, position=6, alt='E')
        db.session.add_all([mut, p, g])

        response = self.client.get(
            '/search/autocomplete_all/?q=BR V6E'
        )
        assert response.json['type'] == 'aminoacid mutation'

        response = self.client.get(
            '/search/autocomplete_all/?q=BR V6'
        )
        assert response.json['type'] == 'message'
        assert 'Awaiting for <code>{alt}</code>' in response.json['entries'][0]['name']

        response = self.client.get(
            '/search/autocomplete_all/?q=BR V'
        )
        assert response.json['type'] == 'message'
        assert 'Awaiting for <code>{pos}{alt}</code>' in response.json['entries'][0]['name']

    def test_save_search(self):
        test_query = 'chr18 19282310 T C'

        self.login('user@domain.org', 'password', create=True)

        save_response = self.search_mutations(
            mutations=test_query,
            store_on_server=True,
            dataset_name='Test Dataset'
        )

        assert save_response.status_code == 200

        # if user saved a dataset, it should be listed in his datasets
        browse_response = self.client.get('/my_datasets/')
        assert browse_response.status_code == 200
        assert b'Test Dataset' in browse_response.data

        # and it should be accessible directly
        dataset = UsersMutationsDataset.query.filter_by(name='Test Dataset').one()
        browse_response = self.client.get('search/saved/%s' % dataset.uri)
        assert browse_response.status_code == 200
        assert b'Test Dataset' in browse_response.data

        self.logout()

        # forbidden from outside
        browse_response = self.client.get('search/saved/%s' % dataset.uri)
        assert browse_response.status_code == 401

        # forbidden for strangers
        self.login('onther_user@domain.org', 'password', create=True)
        browse_response = self.client.get('search/saved/%s' % dataset.uri)
        assert browse_response.status_code == 401
        self.logout()

        # it's still allowed to save data on server without logging in,
        # but then user will not be able to browse these as datasets.
        unauthorized_save_response = self.search_mutations(
            mutations=test_query,
            store_on_server=True,
            dataset_name='Test Dataset'
        )

        assert unauthorized_save_response.status_code == 200
