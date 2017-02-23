from imports.protein_data import active_driver_gene_lists as load_active_driver_gene_lists
from database_testing import DatabaseTest
from miscellaneous import make_named_temp_file


raw_gene_list = """\
"","gene","p","fdr","n_pSNVs","cancer_type","is_cancer_gene"
"1","AHNAK",4.49525859881237e-15,2.58702132361652e-11,9,"blca",0
"2","TP53",3.16436780231519e-09,9.10546835116197e-06,23,"blca",1
"3","ESR1",6.56797363279669e-06,0.00104523142890679,9,"PAN",0
"4","ANK2",6.7487888396638e-06,0.00105647981592011,23,"PAN",0
"5","LRRK2",7.46023452647159e-06,0.00105647981592011,23,"PAN",0
"6","PLEC",7.40940639686046e-06,0.00105647981592011,13,"PAN",0
"7","PCM1",7.46848765304348e-06,0.00105647981592011,6,"PAN",1
"8","TP53BP1",7.30226175024374e-06,0.00105647981592011,15,"PAN",0
"9","MDC1",1.82129092288826e-06,0.001164614362358,7,"blca",0'\
"""


class TestImport(DatabaseTest):

    def test_gene_lists(self):

        filename = make_named_temp_file(raw_gene_list)

        with self.app.app_context():
            gene_lists = load_active_driver_gene_lists(lists=(
                ('TCGA', filename),
            ))

        # one gene list returned (TCGA)
        assert len(gene_lists) == 1

        gene_list = gene_lists[0]

        # correct name of gene list
        assert gene_list.name == 'TCGA'

        # only entries with "PAN" should be extracted
        assert len(gene_list.entries) == 6

        # let's take some entry
        an_entry = gene_list.entries[0]

        assert type(an_entry.p) is float
