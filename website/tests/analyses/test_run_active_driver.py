from functools import partial
from math import inf

from pandas import Series

from analyses import active_driver
from analyses.enrichment import active_driver_genes_enrichment
from database import db
from miscellaneous import make_named_temp_file
from models import Mutation, Site, Protein, MC3Mutation, Gene, SiteType, Cancer
from database_testing import DatabaseTest


# just four as the goal is not to comprehensively test AD, but just to check if it runs ok
sequences = {
    'NM_000546': 'MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGPDEAPRMPEAAPPVAPAPAAPTPAAPAPAPSWPLSSSVPSQKTYQGSYGFRLGFLHSGTAKSVTCTYSPALNKMFCQLAKTCPVQLWVDSTPPPGTRVRAMAIYKQSQHMTEVVRRCPHHERCSDSDGLAPPQHLIRVEGNLRVEYLDDRNTFRHSVVVPYEPPEVGSDCTTIHYNYMCNSSCMGGMNRRPILTIITLEDSSGNLLGRNSFEVRVCACPGRDRRTEEENLRKKGEPHHELPPGSTKRALPNNTSSSPQPKKKPLDGEYFTLQIRGRERFEMFRELNEALELKDAQAGKEPGGSRAHSSHLKSKKGQSTSRHKKLMFKTEGPDSD',
    'NM_001961': 'MVNFTVDQIRAIMDKKANIRNMSVIAHVDHGKSTLTDSLVCKAGIIASARAGETRFTDTRKDEQERCITIKSTAISLFYELSENDLNFIKQSKDGAGFLINLIDSPGHVDFSSEVTAALRVTDGALVVVDCVSGVCVQTETVLRQAIAERIKPVLMMNKMDRALLELQLEPEELYQTFQRIVENVNVIISTYGEGESGPMGNIMIDPVLGTVGFGSGLHGWAFTLKQFAEMYVAKFAAKGEGQLGPAERAKKVEDMMKKLWGDRYFDPANGKFSKSATSPEGKKLPRTFCQLILDPIFKVFDAIMNFKKEETAKLIEKLDIKLDSEDKDKEGKPLLKAVMRRWLPAGDALLQMITIHLPSPVTAQKYRCELLYEGPPDDEAAMGIKSCDPKGPLMMYISKMVPTSDKGRFYAFGRVFSGLVSTGLKVRIMGPNYTPGKKEDLYLKPIQRTILMMGRYVEPIEDVPCGNIVGLVGVDQFLVKTGTITTFEHAHNMRVMKFSVSPVVRVAVEAKNPADLPKLVEGLKRLAKSDPMVQCIIEESGEHIIAGAGELHLEICLKDLEEDHACIPIKKSDPVVSYRETVSEESNVLCLSKSPNKHNRLYMKARPFPDGLAEDIDKGEVSARQELKQRARYLAEKYEWDVAEARKIWCFGPDGTGPNILTDITKGVQYLNEIKDSVVAGFQWATKEGALCEENMRGVRFDVHDVTLHADAIHRGGGQIIPTARRCLYASVLTAQPRLMEPIYLVEIQCPEQVVGGIYGVLNRKRGHVFEESQVAGTPMFVVKAYLPVNESFGFTADLRSNTGGQAFPQCVFDHWQILPGDPFDNSSRPSQVVAETRKRKGLKEGIPALDNFLDKL',
    'NM_000285': 'MAAATGPSFWLGNETLKVPLALFALNRQRLCERLRKNPAVQAGSIVVLQGGEETQRYCTDTGVLFRQESFFHWAFGVTEPGCYGVIDVDTGKSTLFVPRLPASHATWMGKIHSKEHFKEKYAVDDVQYVDEIASVLTSQKPSVLLTLRGVNTDSGSVCREASFDGISKFEVNNTILHPEIVECRVFKTDMELEVLRYTNKISSEAHREVMKAVKVGMKEYELESLFEHYCYSRGGMRHSSYTCICGSGENSAVLHYGHAGAPNDRTIQNGDMCLFDMGGEYYCFASDITCSFPANGKFTADQKAVYEAVLRSSRAVMGAMKPGVWWPDMHRLADRIHLEELAHMGILSGSVDAMVQAHLGAVFMPHGLGHFLGIDVHDVGGYPEGVERIDEPGLRSLRTARHLQPGMVLTVEPGIYFIDHLLDEALADPARASFLNREVLQRFRGFGGVRIEEDVVVTDSGIELLTCVPRTVEEIEACMAGCDKAFTPFSGPK*',
    'NM_004435': 'MRALRAGLTLASGAGLGAVVEGWRRRREDARAAPGLLGRLPVLPVAAAAELPPVPGGPRGPGELAKYGLPGLAQLKSRESYVLCYDPRTRGALWVVEQLRPERLRGDGDRRECDFREDDSVHAYHRATNADYRGSGFDRGHLAAAANHRWSQKAMDDTFYLSNVAPQVPHLNQNAWNNLEKYSRSLTRSYQNVYVCTGPLFLPRTEADGKSYVKYQVIGKNHVAVPTHFFKVLILEAAGGQIELRTYVMPNAPVDEAIPLERFLVPIESIERASGLLFVPNILARAGSLKAITAGSK',
}

disorder = {
    'NM_000546': '111111111111111111111111111111111111110000000000111101111111111111111111111111111111111111111110000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000111111111111111111111111111111111100000000000000000000000000000000001111111111111111111111111111111111',
    'NM_001961': '100000000000000000000000000000000000000000000000000000000111111111111111110000000000000000000000000000000001000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001000000000000',
    'NM_000285': '1111110000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001111111111*',
    'NM_004435': '111111111111111111111111111111111111111111111111111111111000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000010000111',
}

protein_to_gene = {
    'NM_000546': 'TP53',
    'NM_001961': 'EEF2',
    'NM_000285': 'PEPD',
    'NM_004435': 'ENDOG'
}

phosphorylations = {
    # many sites and many PTM mutations
    'TP53': [
        6, 9, 15, 18, 20, 33, 37, 46, 55, 81, 99, 106, 126, 149, 150, 155, 183, 211, 215,
        220, 249, 269, 284, 304, 312, 313, 314, 315, 327, 366, 371, 376, 377, 378, 387, 392
    ],
    # many sites and few PTM mutations
    'EEF2': [
        23, 38, 48, 54, 57, 59, 177, 265, 274, 288, 325, 360, 373, 399, 411, 418, 435, 443,
        450, 500, 502, 579, 582, 584, 587, 593, 595, 623, 671, 678, 724, 732, 745, 779, 793, 802
    ],
    # few sites and no PTM mutations
    'PEPD': [167, 188, 487, 490],

    # no sites
    'ENDOG': []
}

mutations_count = {'TP53': 189, 'EEF2': 3, 'PEPD': 3, 'ENDOG': 0}

ptm_mutations_count = {'TP53': 139, 'EEF2': 1, 'PEPD': 0, 'ENDOG': 0}


cancer_census = """\
gene_symbol
TP53
CYSLTR2
"""


def load_cancer_data():

    genes = {
        name: Gene(name=name)
        for name in protein_to_gene.values()
    }

    proteins = {
        name: Protein(refseq=refseq, sequence=sequence, gene=genes[name], disorder_map=disorder[refseq])
        for refseq, sequence in sequences.items()
        for name in [protein_to_gene[refseq]]
    }

    for protein in proteins.values():
        protein.gene.preferred_isoform = protein

    phosphorylation = SiteType(name='phosphorylation')

    phosphosite = partial(Site, types={phosphorylation})

    sites = {
        phosphosite(position=position, residue=protein.sequence[position - 1], protein=protein)
        for name, positions in phosphorylations.items()
        for position in positions
        for protein in [proteins[name]]
    }

    mutations = {}

    def mutation_for(protein, position):
        key = (protein, position)
        if key not in mutations:
            mutations[key] = Mutation(position=position, alt='X', protein=protein)
        return mutations[key]

    cancer = Cancer(name='Cancer 1', code='CA1')
    cancer_mutation = partial(MC3Mutation, cancer=cancer, count=1)

    cancer_mutations = [
        # PTM mutations
        *[
            cancer_mutation(mutation=mutation_for(protein, positions[i]))
            for name, protein in proteins.items()
            for positions in [[
                position + shift
                for position in phosphorylations[name]
                for shift in range(-7, 8)
                if 0 < position + shift < protein.length
            ]]
            for i in range(ptm_mutations_count[name])
        ],
        # all other mutations
        *[
            cancer_mutation(mutation=mutation_for(protein, positions[i]))
            for name, protein in proteins.items()
            for positions in [[
                position
                for position in range(protein.length)
                if (Series(phosphorylations[name]) - position).abs().min() > 7
            ]]
            for i in range(mutations_count[name] - ptm_mutations_count[name])
        ]
    ]

    db.session.add_all(cancer_mutations)
    db.session.add_all(proteins.values())
    db.session.add_all(genes.values())
    db.session.add_all(sites)
    db.session.commit()

    return phosphorylation


class ActiveDriverTest(DatabaseTest):

    def test_pan_cancer_analysis(self):

        phosphorylation = load_cancer_data()

        top_results = active_driver.pan_cancer_analysis(phosphorylation, gprofiler=False, progress_bar=False)
        top = top_results['top_fdr']

        assert len(top) == 1
        significant = top.iloc[0]

        assert significant.gene == 'TP53'
        # by default, the list should be trimmed at FDR cutoff of 0.05
        assert significant.fdr <= 0.05

        results = active_driver.pan_cancer_analysis(phosphorylation, gprofiler=False, fdr_cutoff=inf, progress_bar=False)
        full = results['top_fdr']

        assert len(full) == 2
        p = full.set_index('gene').p
        assert p['TP53'] < p['EEF2']

    def test_active_driver_genes_enrichment(self):

        phosphorylation = load_cancer_data()

        top_results = active_driver.pan_cancer_analysis(phosphorylation, gprofiler=False, progress_bar=False)

        g = Gene(name='CYSLTR2')
        p = Protein(refseq='NM_020377', gene=g)
        db.session.add_all([g, p])

        census_path = make_named_temp_file(cancer_census)
        (
            observed_count, expected_count,
            contingency_table, oddsratio, pvalue
        ) = active_driver_genes_enrichment(top_results, cancer_census_path=census_path)

        assert observed_count == 1
        # TODO: create more comprehensive example to validate remaining values
