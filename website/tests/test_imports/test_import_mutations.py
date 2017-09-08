import gzip
from imports.mutations import MutationImportManager, MutationImporter
from database_testing import DatabaseTest
from models import Protein, InheritedMutation, Disease
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


clinvar_mutations = """\
Chr	Start	End	Ref	Alt	Func.refGene	Gene.refGene	GeneDetail.refGene	ExonicFunc.refGene	AAChange.refGene	V11	V12	V13	V14	V15	V16	V17	V18	V19	V20	V21
17	7572973	7572973	C	A	exonic	TP53	.	nonsynonymous SNV	TP53:NM_001126115:exon7:c.G740T:p.R247L,TP53:NM_001276697:exon7:c.G659T:p.R220L,TP53:NM_001126118:exon10:c.G1019T:p.R340L,TP53:NM_000546:exon11:c.G1136T:p.R379L,TP53:NM_001126112:exon11:c.G1136T:p.R379L,TP53:NM_001276760:exon11:c.G1019T:p.R340L,TP53:NM_001276761:exon11:c.G1019T:p.R340L	.	.	.	17	7572973	rs863224682	C	A	.	.	RS=863224682;RSPOS=7572973;RV;dbSNPBuildID=146;SSR=0;SAO=1;VP=0x050060800a05000002100100;GENEINFO=TP53:7157;WGT=1;VC=SNV;PM;NSM;REF;U3;ASP;LSD;CLNALLE=1;CLNHGVS=NC_000017.10:g.7572973C>A;CLNSRC=.;CLNORIGIN=1;CLNSRCID=.;CLNSIG=0|0;CLNDSDB=MedGen:Orphanet:SNOMED_CT|MedGen:OMIM:ORPHA;CLNDSDBID=C0085390:ORPHA524:428850001|C3280492:614327:289539;CLNDBN=Li-Fraumeni_syndrome|Tumor_predisposition_syndrome;CLNREVSTAT=single|single;CLNACC=RCV000199273.1|RCV000219990.1
17	7573987	7573987	G	T	exonic	TP53	.	nonsynonymous SNV	TP53:NM_001126115:exon6:c.C644A:p.A215D,TP53:NM_001276697:exon6:c.C563A:p.A188D,TP53:NM_001126118:exon9:c.C923A:p.A308D,TP53:NM_000546:exon10:c.C1040A:p.A347D,TP53:NM_001126112:exon10:c.C1040A:p.A347D,TP53:NM_001276760:exon10:c.C923A:p.A308D,TP53:NM_001276761:exon10:c.C923A:p.A308D	.	.	.	17	7573987	rs397516434	G	T	.	.	RS=397516434;RSPOS=7573987;RV;dbSNPBuildID=138;SSR=0;SAO=1;VP=0x050060800a05000002100100;GENEINFO=TP53:7157;WGT=1;VC=SNV;PM;NSM;REF;U3;ASP;LSD;CLNALLE=1;CLNHGVS=NC_000017.10:g.7573987G>T;CLNSRC=.;CLNORIGIN=1;CLNSRCID=.;CLNSIG=0;CLNDSDB=MedGen;CLNDSDBID=CN169374;CLNDBN=not_specified;CLNREVSTAT=no_criteria;CLNACC=RCV000036529.2
17	7576914	7576914	T	C	exonic	TP53	.	nonsynonymous SNV	TP53:NM_001126115:exon5:c.A536G:p.N179S,TP53:NM_001126116:exon5:c.A536G:p.N179S,TP53:NM_001126117:exon5:c.A536G:p.N179S,TP53:NM_001276697:exon5:c.A455G:p.N152S,TP53:NM_001276698:exon5:c.A455G:p.N152S,TP53:NM_001276699:exon5:c.A455G:p.N152S,TP53:NM_001126118:exon8:c.A815G:p.N272S,TP53:NM_000546:exon9:c.A932G:p.N311S,TP53:NM_001126112:exon9:c.A932G:p.N311S,TP53:NM_001126113:exon9:c.A932G:p.N311S,TP53:NM_001126114:exon9:c.A932G:p.N311S,TP53:NM_001276695:exon9:c.A815G:p.N272S,TP53:NM_001276696:exon9:c.A815G:p.N272S,TP53:NM_001276760:exon9:c.A815G:p.N272S,TP53:NM_001276761:exon9:c.A815G:p.N272S	.	.	.	17	7576914	rs56184981	T	C,G	.	.	RS=56184981;RSPOS=7576914;dbSNPBuildID=129;SSR=0;SAO=1;VP=0x050268000a05000002100100;GENEINFO=TP53:7157;WGT=1;VC=SNV;PM;PMC;S3D;NSM;REF;ASP;LSD;CLNALLE=2;CLNHGVS=NC_000017.10:g.7576914T>G;CLNSRC=.;CLNORIGIN=1;CLNSRCID=.;CLNSIG=0;CLNDSDB=MedGen:Orphanet:SNOMED_CT;CLNDSDBID=C0085390:ORPHA524:428850001;CLNDBN=Li-Fraumeni_syndrome;CLNREVSTAT=single;CLNACC=RCV000205077.1
"""

# Mocked: for test simplicity hypermutated sample is the one more than two mutations.
# The first three mutations are from the same sample, the last one is from different one.
with_hypermutated_samples = """\
11	124489539	124489539	G	A	exonic	PANX3	.	nonsynonymous SNV	PANX3:NM_052959:exon4:c.G887A:p.R296Q	TCGA-02-0003-01A-01D-1490-08
11	47380512	47380512	G	T	exonic;exonic	SPI1	.	nonsynonymous SNV;nonsynonymous SNV	SPI1:NM_001080547:exon4:c.C379A:p.P127T,SPI1:NM_003120:exon4:c.C376A:p.P126T	TCGA-02-0003-01A-01D-1490-08
11	89868837	89868837	C	T	exonic;exonic	NAALAD2	.	nonsynonymous SNV;nonsynonymous SNV	NAALAD2:NM_001300930:exon2:c.C193T:p.R65C,NAALAD2:NM_005467:exon2:c.C193T:p.R65C	TCGA-02-0003-01A-01D-1490-08
1	17418969	17418969	C	T	exonic	PADI2	.	nonsynonymous SNV	PADI2:NM_007365:exon6:c.G589A:p.G197R	TCGA-04-1349-01A-01W-0492-08
"""


def create_proteins(data):
    return {
        refseq_nm: Protein(refseq=refseq_nm, sequence=sequence)
        for refseq_nm, sequence in data.items()
    }


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

        proteins = create_proteins(protein_data)

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

    def test_hypermutated_finder(self):
        from statistics import hypermutated_samples
        muts_filename = make_named_temp_file(
            data=with_hypermutated_samples.encode(),
            mode='wb',
            opener=gzip.open
        )
        samples = hypermutated_samples(muts_filename, threshold=2)
        # there should be one hypermutated sample
        assert len(samples) == 1

        sample, count = samples.popitem()
        assert sample == 'TCGA-02-0003-01A-01D-1490-08'
        assert count == 3

    def test_clinvar_import(self):
        muts_filename = make_named_temp_file(
            data=clinvar_mutations.encode(),
            mode='wb',
            opener=gzip.open
        )
        protein_data = {
            'NM_000546': 'MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGPDEAPRMPEAAPPVAPAPAAPTPAAPAPAPSWPLSSSVPSQKTYQGSYGFRLGFLHSGTAKSVTCTYSPALNKMFCQLAKTCPVQLWVDSTPPPGTRVRAMAIYKQSQHMTEVVRRCPHHERCSDSDGLAPPQHLIRVEGNLRVEYLDDRNTFRHSVVVPYEPPEVGSDCTTIHYNYMCNSSCMGGMNRRPILTIITLEDSSGNLLGRNSFEVRVCACPGRDRRTEEENLRKKGEPHHELPPGSTKRALPNNTSSSPQPKKKPLDGEYFTLQIRGRERFEMFRELNEALELKDAQAGKEPGGSRAHSSHLKSKKGQSTSRHKKLMFKTEGPDSD*'
        }
        proteins = create_proteins(protein_data)

        with self.app.app_context():
            source_name = 'clinvar'
            # let's pretend that we already have some proteins in our db
            db.session.add_all(proteins.values())
            db.session.commit()

            muts_import_manager.perform(
                'load', proteins, [source_name], {source_name: muts_filename}
            )

            mutations = InheritedMutation.query.all()
            # the second mutations has "not_specified" disease, should be skipped
            assert len(mutations) == 2

            first_row_mutation = proteins['NM_000546'].mutations[1]
            assert first_row_mutation.position == 379
            assert first_row_mutation.alt == 'L'

            diseases = Disease.query.all()
            assert len(diseases) == 2

            clinvar = first_row_mutation.meta_ClinVar
            assert clinvar.db_snp_ids == [863224682]  # rs863224682
            assert not clinvar.is_validated
            assert not clinvar.is_low_freq_variation

            assert clinvar.sig_code == [0, 0]
            assert clinvar.disease_name == ['Li-Fraumeni syndrome', 'Tumor predisposition syndrome']

            assert first_row_mutation.sig_code == [0, 0]
            assert first_row_mutation.disease_name == ['Li-Fraumeni syndrome', 'Tumor predisposition syndrome']

            third_row_mutation = proteins['NM_000546'].mutations[0]
            assert third_row_mutation.meta_ClinVar.disease_name == ['Li-Fraumeni syndrome']

    def test_duplicates_finder(self):

        # make a simple, dummy and concrete Importer
        class Importer(MutationImporter):
            insert_keys = ['effect', 'some_db_id']

            def insert_details(self, data): pass

            def parse(self, path): pass

        importer = Importer()
        mutation_details = []

        def add_if_not_duplicate(mutation_id, details):
            is_duplicated = importer.look_after_duplicates(mutation_id, mutation_details, details)
            if not is_duplicated:
                details_with_id = [mutation_id]
                details_with_id.extend(details)
                mutation_details.append(details_with_id)
            return is_duplicated

        # let's add a simple mutation details for mutation with id 1 and with id 2:
        for mutation_id in [1, 2]:
            duplicated = add_if_not_duplicate(mutation_id, ['motif_lost', 11])
            assert not duplicated

        # will we catch a duplicate?
        duplicated = add_if_not_duplicate(2, ['motif_lost', 11])
        assert duplicated

        # what about different mutation details? Will it be allowed (as it differs from the one already stored)?
        duplicated = add_if_not_duplicate(2, ['motif_gain', 22])
        assert not duplicated


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
