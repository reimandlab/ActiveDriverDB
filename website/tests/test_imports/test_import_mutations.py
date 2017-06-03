import gzip
from imports.mutations import MutationImportManager
from database_testing import DatabaseTest
from models import Protein
from models import MC3Mutation
from database import db
from miscellaneous import make_named_temp_file


muts_import_manager = MutationImportManager()


# this is modified output of `zcat data/mutations/mc3_muts_annotated.txt.gz | head`
mc3_mutations = """\
11	124489539	124489539	G	A	exonic	PANX3	.	nonsynonymous SNV	PANX3:NM_052959:exon4:c.G887A:p.R296Q	TCGAA-02-0003-01A-01D-1490-08
11	47380512	47380512	G	T	exonic;exonic	SPI1	.	nonsynonymous SNV;nonsynonymous SNV	SPI1:NM_001080547:exon4:c.C379A:p.P127T,SPI1:NM_003120:exon4:c.C376A:p.P126T	TCGA-02-0003-01A-01D-1490-08
11	89868837	89868837	C	T	exonic;exonic	NAALAD2	.	nonsynonymous SNV;nonsynonymous SNV	NAALAD2:NM_001300930:exon2:c.C193T:p.R65C,NAALAD2:NM_005467:exon2:c.C193T:p.R65C	TCGA-02-0003-01A-01D-1490-08
12	107371855	107371855	A	G	exonic	MTERF2	.	nonsynonymous SNV	MTERF2:NM_001033050:exon3:c.T638C:p.L213S,MTERF2:NM_025198:exon3:c.T638C:p.L213S	TCGA-02-0003-01A-01D-1490-08
12	108012011	108012011	G	A	exonic	BTBD11	.	nonsynonymous SNV	BTBD11:NM_001017523:exon8:c.G919A:p.E307K,BTBD11:NM_001018072:exon10:c.G2308A:p.E770K	TCGA-02-0003-01A-01D-1490-08
12	8082458	8082458	C	T	exonic;exonic	SLC2A3	.	nonsynonymous SNV;nonsynonymous SNV	SLC2A3:NM_006931:exon6:c.G683A:p.R228Q;SLC2A3:NM_006931:exon6:c.G683A:p.R228Q	TCGA-02-0003-01A-01D-1490-08
14	100363606	100363606	G	A	exonic	EML1	.	nonsynonymous SNV	EML1:NM_004434:exon7:c.G802A:p.A268T,EML1:NM_001008707:exon8:c.G859A:p.A287T	TCGA-02-0003-01A-01D-1490-08
14	33290999	33290999	A	G	exonic	AKAP6	.	nonsynonymous SNV	AKAP6:NM_004274:exon13:c.A3980G:p.D1327G	TCGA-02-0003-01A-01D-1490-08
"""

# assuming that there was mistyped sample name for first mutation,
# here it is an updated file with one record: this one updated mutation
# also a new mutation (the same pos, G>T) has been found to be important
# and we want it to be added
mc3_mutations_updated = """\
11	124489539	124489539	G	A	exonic	PANX3	.	nonsynonymous SNV	PANX3:NM_052959:exon4:c.G887A:p.R296Q	TCGA-02-0003-01A-01D-1490-08
11	124489539	124489539	G	T	exonic	PANX3	.	nonsynonymous SNV	PANX3:NM_052959:exon4:c.G887T:p.R296L	TCGA-02-0003-01A-01D-1490-08
"""

class TestImport(DatabaseTest):

    def test_tcga_import(self):

        muts_filename = make_named_temp_file(
            data=mc3_mutations.encode(),
            mode='wb',
            opener=gzip.open
        )

        update_filename = make_named_temp_file(
            data=mc3_mutations_updated.encode(),
            mode='wb',
            opener=gzip.open
        )

        # create proteins from first three data rows
        protein_data = {
            'NM_052959': 'MSLAHTAAEYMLSDALLPDRRGPRLKGLRLELPLDRIVKFVAVGSPLLLMSLAFAQEFSSGSPISCFSPSNFSIRQAAYVDSSCWDSLLHHKQDGPGQDKMKSLWPHKALPYSLLALALLMYLPVLLWQYAAVPALSSDLLFIISELDKSYNRSIRLVQHMLKIRQKSSDPYVFWNELEKARKERYFEFPLLERYLACKQRSHSLVATYLLRNSLLLIFTSATYLYLGHFHLDVFFQEEFSCSIKTGLLSDETHVPNLITCRLTSLSIFQIVSLSSVAIYTILVPVIIYNLTRLCRWDKRLLSVYEMLPAFDLLSRKMLGCPINDLNVILLFLRANISELISFSWLSVLCVLKDTTTQKHNIDTVVDFMTLLAGLEPSKPKHLTNSACDEHP',
            'NM_001080547': 'MLQACKMEGFPLVPPQPSEDLVPYDTDLYQRQTHEYYPYLSSDGESHSDHYWDFHPHHVHSEFESFAENNFTELQSVQPPQLQQLYRHMELEQMHVLDTPMVPPHPSLGHQVSYLPRMCLQYPSLSPAQPSSDEEEGERQSPPLEVSDGEADGLEPGPGLLPGETGSKKKIRLYQFLLDLLRSGDMKDSIWWVDKDKGTFQFSSKHKEALAHRWGIQKGNRKKMTYQKMARALRNYGKTGEVKKVKKKLTYQFSGEVLGRGGLAERRHPPH',
            'NM_003120': 'MLQACKMEGFPLVPPPSEDLVPYDTDLYQRQTHEYYPYLSSDGESHSDHYWDFHPHHVHSEFESFAENNFTELQSVQPPQLQQLYRHMELEQMHVLDTPMVPPHPSLGHQVSYLPRMCLQYPSLSPAQPSSDEEEGERQSPPLEVSDGEADGLEPGPGLLPGETGSKKKIRLYQFLLDLLRSGDMKDSIWWVDKDKGTFQFSSKHKEALAHRWGIQKGNRKKMTYQKMARALRNYGKTGEVKKVKKKLTYQFSGEVLGRGGLAERRHPPH',
            'NM_001300930': 'MAESRGRLYLWMCLAAALASFLMGFMVGWFIKPLKETTTSVRYHQSIRWKLVSEMKAENIKSFLRSFTKLPHLAGTEQNFLLAKKIQTQWKKFGLDSAKLVHYDVLLSYPNETNANYISIVDEHETEIFKTSYLEPPPDGYENVTNIVPPYNAFSAQGMPEGDLVYVNYARTEDFFKLEREMGINCTGKIVIARYGKIFRGNKVKNAMLAGAIGIILYSDPADYFAPEVQPYPKGWNLPGTAAQRGNVLNLNGAGDPLTPGYPAKEYTFRLDVEEGVGIPRIPVHPIGYNDAEILLRKVRMHVYNINKITRIYNVVGTIRGSVEPDRYVILGGHRDSWVFGAIDPTSGVAVLQEIARSFGKLMSKGWRPRRTIIFASWDAEEFGLLGSTEWAEENVKILQERSIAYINSDSSIEGNYTLRVDCTPLLYQLVYKLTKEIPSPDDGFESKSLYESWLEKDPSPENKNLPRINKLGSGSDFEAYFQRLGIASGRARYTKNKKTDKYSSYPVYHTIYETFELVEKFYDPTFKKQLSVAQLRGALVYELVDSKIIPFNIQDYAEALKNYAASIYNLSKKHDQQLTDHGVSFDSLFSAVKNFSEAASDFHKRLIQVDLNNPIAVRMMNDQLMLLERAFIDPLGLPGKLFYRHIIFAPSSHNKYAGESFPGIYDAIFDIENKANSRLAWKEVKKHISIAAFTIQAAAGTLKEVL',
            'NM_005467': 'MAESRGRLYLWMCLAAALASFLMGFMVGWFIKPLKETTTSVRYHQSIRWKLVSEMKAENIKSFLRSFTKLPHLAGTEQNFLLAKKIQTQWKKFGLDSAKLVHYDVLLSYPNETNANYISIVDEHETEIFKTSYLEPPPDGYENVTNIVPPYNAFSAQGMPEGDLVYVNYARTEDFFKLEREMGINCTGKIVIARYGKIFRGNKVKNAMLAGAIGIILYSDPADYFAPEVQPYPKGWNLPGTAAQRGNVLNLNGAGDPLTPGYPAKEYTFRLDVEEGVGIPRIPVHPIGYNDAEILLRYLGGIAPPDKSWKGALNVSYSIGPGFTGSDSFRKVRMHVYNINKITRIYNVVGTIRGSVEPDRYVILGGHRDSWVFGAIDPTSGVAVLQEIARSFGKLMSKGWRPRRTIIFASWDAEEFGLLGSTEWAEENVKILQERSIAYINSDSSIEGNYTLRVDCTPLLYQLVYKLTKEIPSPDDGFESKSLYESWLEKDPSPENKNLPRINKLGSGSDFEAYFQRLGIASGRARYTKNKKTDKYSSYPVYHTIYETFELVEKFYDPTFKKQLSVAQLRGALVYELVDSKIIPFNIQDYAEALKNYAASIYNLSKKHDQQLTDHGVSFDSLFSAVKNFSEAASDFHKRLIQVDLNNPIAVRMMNDQLMLLERAFIDPLGLPGKLFYRHIIFAPSSHNKYAGESFPGIYDAIFDIENKANSRLAWKEVKKHISIAAFTIQAAAGTLKEVL'
        }

        proteins = {
            refseq_nm: Protein(refseq=refseq_nm, sequence=sequence)
            for refseq_nm, sequence in protein_data.items()
        }

        with self.app.app_context():
            source_name = 'mc3'
            # let's pretend that we already have some proteins in our db
            db.session.add_all(proteins.values())

            muts_import_manager.perform(
                'load', proteins, [source_name], {source_name: muts_filename}
            )

            # there are data for 13 mutations but there are only 5 proteins in database.
            # For each of this proteins there is only one mutations so only 5 mutations will be loaded
            cancer_mutations = MC3Mutation.query.all()
            assert len(cancer_mutations) == 5

            first_row_mutation = proteins['NM_052959'].mutations[0]
            assert first_row_mutation.position == 296
            assert first_row_mutation.alt == 'Q'

            mc3_mutation = first_row_mutation.meta_MC3[0]
            assert mc3_mutation.samples == 'TCGAA-02-0003-01A-01D-1490-08'

            muts_import_manager.perform(
                'update', proteins, [source_name], {source_name: update_filename}
            )

            # updated correctly?
            assert mc3_mutation.samples == 'TCGA-02-0003-01A-01D-1490-08'

            # added correctly during update?
            assert len(list(proteins['NM_052959'].mutations)) == 2
            cancer_mutations = MC3Mutation.query.all()
            assert len(cancer_mutations) == 6

            # select the new mutation:
            new_mutation = None
            for mutation in proteins['NM_052959'].mutations:
                if mutation != mc3_mutation:
                    new_mutation = mutation
            assert new_mutation
            # check correctness:
            assert new_mutation.position == 296
            assert new_mutation.alt == 'L'
            new_mc3_mutation = first_row_mutation.meta_MC3[0]
            assert new_mc3_mutation.samples == 'TCGA-02-0003-01A-01D-1490-08'


tss_cancer_map_text = """\
A1	Breast invasive carcinoma
A2	Breast invasive carcinoma
A3	Kidney renal cell carcinoma
"""


def test_tss_cancer_map():
    from imports.mutations.mc3 import load_tss_cancer_map

    tss_filename = make_named_temp_file(
        data=tss_cancer_map_text
    )

    tss_map = load_tss_cancer_map(tss_filename)

    assert type(tss_map) is dict
    assert tss_map['A1'] == 'Breast invasive carcinoma'
    assert tss_map['A3'] == 'Kidney renal cell carcinoma'
