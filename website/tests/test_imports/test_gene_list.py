from imports.protein_data import active_driver_gene_lists as load_active_driver_gene_lists, ListData
from database_testing import DatabaseTest
from miscellaneous import make_named_temp_file
from database import db
from models import TCGAMutation

# merged:
# head ActiveDriver1_result_pvalue_less_0.01_CancerMutation-2017-02-16.txt -n 4
# head ActiveDriver1_result_pvalue_less_0.01_CancerMutation-2017-02-16.txt -n 500 | tail

raw_gene_list = """\
gene	p	fdr
CTNNB1	7.29868558025906e-65	8.70368255445893e-61
IDH1	5.94998080805889e-63	3.54767605680511e-59
PTEN	1.82282073049743e-51	7.2457124037273e-48
HSPA4	0.000408236641023006	0.00991696688939805
SHC1	0.000408768573301514	0.00991696688939805
TERF2	0.000409152847763844	0.00991696688939805
XPO1	0.000412399692346554	0.00995819609074201
PNPT1	0.000412524014157363	0.00995819609074201
TMEM131	0.000424693241746104	0.0102312462784289
KRT75	0.000429521905278659	0.0103267111299355
ALDH2	0.000431112122924959	0.0103440886637427
ADGRL1	0.000433144270973498	0.0103710604881763
LRMP	0.000433975612880499	0.0103710604881763\
"""


class TestImport(DatabaseTest):

    def test_gene_lists(self):

        filename = make_named_temp_file(raw_gene_list)

        with self.app.app_context():
            gene_lists = load_active_driver_gene_lists(lists=(
                ListData(
                    name='TCGA list', path=filename, mutations_source=TCGAMutation,
                    site_type_name='all'
                ),
            ))

        # one gene list returned (TCGA)
        assert len(gene_lists) == 1

        gene_list = gene_lists[0]

        # correct name of gene list
        assert gene_list.name == 'TCGA list'

        assert gene_list.mutation_source_name == 'TCGA'

        # let's take some entry
        an_entry = gene_list.entries[0]

        assert type(an_entry.p) is float
        assert type(an_entry.fdr) is float

        genes = [entry.gene.name for entry in gene_list.entries]

        assert 'TMEM131' not in genes
        assert 'PNPT1' in genes

        db.session.add_all(gene_lists)

        with self.app.app_context():
            gene_lists = load_active_driver_gene_lists(lists=(
                ListData(
                    name='TCGA list', path=filename, mutations_source=TCGAMutation,
                    site_type_name='all'
                ),
            ))

        # no duplicate lists should be created
        assert not gene_lists
