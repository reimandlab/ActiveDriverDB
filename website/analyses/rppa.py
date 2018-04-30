from pandas import read_table, MultiIndex
from rpy2.robjects import r, FloatVector
from rpy2.robjects.packages import importr
from statsmodels.distributions import ECDF

from exports.protein_data import ptm_muts_of_gene
from imports.mutations.mc3 import MC3Importer


def load_rppa(path='data/mdanderson.org_PANCAN_MDA_RPPA_Core.RPPA_whitelisted (3).tsv'):
    rppa = read_table(path)
    rppa = rppa.rename(columns={'Unnamed: 0': 'gene'})
    rppa = rppa.set_index(['gene'])
    return rppa


def differential_expression_ptm_muts(gene, modification_type):
    tcga_importer = MC3Importer()
    extract_cancer_name = tcga_importer.extract_cancer_name

    rppa = load_rppa()

    muts = ptm_muts_of_gene(
        gene=gene, site_type=modification_type,
        mutation_source='mc3', export_samples=True,
        to_csv=False
    )

    expression_distributions = {
        sample: ECDF(rppa[sample].values)
        for sample in rppa.columns
    }

    wilcox = r['wilcox.test']
    stats = importr('stats')

    rppa.columns = MultiIndex.from_tuples(
        [(extract_cancer_name(sample), sample) for sample in rppa.columns],
        names=['cancer_name', 'sample_id']
    )
    muts = muts.assign(cancer_name=muts.sample_id.map(extract_cancer_name))

    rppa_cancers = set(rppa.columns.get_level_values('cancer_name'))
    muts_cancers = set(muts.cancer_name)

    if muts_cancers - rppa_cancers:
        print(f'Cancer types: {muts_cancers - rppa_cancers} are not in RPPA data (!)')

    for cancer_name in muts_cancers:
        p_values = []

        # samples that have one of analysed mutations:
        samples_with_muts = set(muts.query('cancer_name == @cancer_name').sample_id)

        cancer_rppa = rppa.xs(cancer_name, level='cancer_name', axis='columns')
        rppa_samples = set(cancer_rppa.columns)

        samples_with_muts_present = samples_with_muts & rppa_samples

        if len(samples_with_muts_present) < 3:
            if len(samples_with_muts) < 3:
                print(f'Skipping {cancer_name} - not enough mutated samples')
                continue
            else:
                print(f'Skipping {cancer_name} - not enough mutated samples having RPPA data')
                print(samples_with_muts_present)
            continue

        samples_without_muts = rppa_samples - samples_with_muts_present

        for gene, data in cancer_rppa.iterrows():
            rppa_carriers = [
                expression_distributions[sample](data[sample])
                for sample in samples_with_muts_present
            ]
            rppa_non_carriers = [
                expression_distributions[sample](data[sample])
                for sample in samples_without_muts
            ]

            result = wilcox(FloatVector(rppa_carriers), FloatVector(rppa_non_carriers))
            p = result.rx("p.value")[0][0]

            p_values.append(p)

        p_adjusted = stats.p_adjust(FloatVector(p_values), method='BH')
        for gene, fdr in zip(cancer_rppa.index, p_adjusted):
            if fdr < 0.2:
                print(gene)
