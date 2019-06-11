from collections import defaultdict
from statistics import mean

from numpy import isnan
from pandas import read_table, MultiIndex, concat
from rpy2.robjects import r, FloatVector
from rpy2.robjects.packages import importr
from statsmodels.distributions import ECDF

from exports.protein_data import ptm_muts_of_gene
from imports.mutations.mc3 import MC3Importer
from models import Cancer
from .active_driver import pan_cancer_analysis, per_cancer_analysis


def extract_antibody(antibody_and_slide):
    antibody = antibody_and_slide[:-4]
    custom_map = {
        'Annexin_I': 'Annexin I',
        'PEA15': 'PEA15',
        'K-Ras': 'KRAS'
    }
    if antibody in custom_map:
        antibody = custom_map[antibody]
    return antibody


def load_rppa(path='data/mdanderson.org_PANCAN_MDA_RPPA_Core.RPPA_whitelisted.tsv'):
    rppa = read_table(path)
    rppa = rppa.rename(columns={'Unnamed: 0': 'antibody'})
    rppa = rppa.set_index(['antibody'])
    rppa.index = rppa.index.map(extract_antibody)
    antibodies = load_antibodies()
    print('Failed to map:')
    print(set(rppa.index) - set(antibodies.antibody))
    rppa.index = rppa.index.map(lambda a: antibodies.query('antibody == @a').iloc[0]['gene'] if a in set(antibodies.antibody) else a)
    return rppa


def load_full_rppa():
    tables = []
    for cancer in Cancer.query:
        try:
            tables.append(
                read_table(f'data/firehose/stddata__2016_07_15/gdac.broadinstitute.org_{cancer.code}.RPPA_AnnotateWithGene.Level_3.2016071500.0.0/{cancer.code}.rppa.txt')
            )
        except FileNotFoundError:
            pass
    rppa = concat(tables)
    rppa = rppa.rename(columns={'Composite.Element.REF': 'antibody'})
    rppa = rppa.set_index(['antibody'])
    rppa.index = rppa.index.map(lambda gene_antibody: gene_antibody.split('|')[0])
    return rppa


def sample_from_aliquot(aliquot):
    return '-'.join(aliquot.split('-')[:4])[:-1]


def load_antibodies(path='data/firehose/gene_antibody_map.txt'):
    """

    Failed attmpts: use 'data/S7.420data20table-S7.4 data table.csv' downloaded and converted from:
    https://tcga-data.nci.nih.gov/docs/publications/stad_2014/S7.4%20data%20table.pdf
    """
    antibodies = read_table(path, names=['gene', 'antibody'], header=None)
    return antibodies


WARNED = False

c = 0
d = set()


def differential_expression_ptm_muts_ad(gene, modification_type, cancer_type, *args, limit_muts=True, **kwargs):
    if cancer_type == 'pan_cancer':
        result = pan_cancer_analysis(modification_type)
    else:
        result = per_cancer_analysis(modification_type)[cancer_type]
        kwargs['cancer_name'] = cancer_type
    if limit_muts:
        muts = result['all_active_mutations']
    else:
        muts = None
    return differential_expression_ptm_muts(gene, modification_type, *args, **kwargs, limit_to_muts=muts)


def differential_expression_ptm_muts(gene, modification_type, cancer_name=None, antibodies=None, limit_to_muts=None, verbose=False, threshold=3):
    tcga_importer = MC3Importer()
    extract_cancer_name = tcga_importer.extract_cancer_name

    rppa = load_rppa()

    muts = ptm_muts_of_gene(
        gene=gene, site_type=modification_type,
        mutation_source='mc3', export_samples=True,
        to_csv=False
    )

    if limit_to_muts is not None:
        limited_muts = {
            (int(mut.position), mut.mut_residue, mut.isoform)
            for mut in limit_to_muts.itertuples(index=False)
        }
        print(len(limited_muts))

        for row in muts.itertuples(index=False):
            k = (int(row.position), row.mut_residue, row.isoform)
            print(k,k in limited_muts)
        print(muts.apply(lambda row: (int(row.position), row.mut_residue, row.isoform) in limited_muts, axis=1))
        muts = muts[muts.apply(lambda row: (int(row.position), row.mut_residue, row.isoform) in limited_muts, axis=1)]
        print(len(muts))

    muts.sample_id = muts.sample_id.map(sample_from_aliquot)

    expression_distributions = {
        sample_from_aliquot(aliquot): ECDF(rppa[aliquot].dropna().values)
        for aliquot in rppa.columns
    }

    multi_aliquot_sampels = set()

    samples = defaultdict(set)

    for aliquot in rppa.columns:
        samples[sample_from_aliquot(aliquot)].add(aliquot)

    global WARNED

    if not WARNED and any(len(occurrences) > 1 for occurrences in samples.values()):
        print('Following samples have data for more than one aliquot:')

        for sample, aliquots in samples.items():
            if len(aliquots) > 1:
                print(sample, aliquots)
                multi_aliquot_sampels.add(sample)

        WARNED = True

    rppa.columns = MultiIndex.from_tuples(
        [
            (extract_cancer_name(aliquot), sample_from_aliquot(aliquot))
            for aliquot in rppa.columns
        ],
        names=['cancer_name', 'sample_id']
    )

    muts = muts.assign(cancer_name=muts.sample_id.map(extract_cancer_name))
    print(muts)

    wilcox = r['wilcox.test']
    stats = importr('stats')

    rppa_cancers = set(rppa.columns.get_level_values('cancer_name'))
    muts_cancers = set(muts.cancer_name)
    if cancer_name:
        muts_cancers = muts_cancers & {cancer_name}

    if muts_cancers - rppa_cancers:
        print(f'Cancer types: {muts_cancers - rppa_cancers} are not in RPPA data (!)')

    suggestive_or_significant = []
    testable_genes = set()

    global c

    for cancer_name in muts_cancers:

        # samples that have one of analysed mutations:
        samples_with_muts = set(muts.query('cancer_name == @cancer_name').sample_id)

        cancer_rppa = rppa.xs(cancer_name, level='cancer_name', axis='columns')
        rppa_samples = set(cancer_rppa.columns)

        samples_with_muts_present = samples_with_muts & rppa_samples
        print(cancer_name, samples_with_muts_present)

        if len(samples_with_muts_present) < threshold:
            if len(samples_with_muts) < threshold:
                # print(f'Skipping {cancer_name} - not enough mutated samples')
                continue
            else:
                # print(f'Skipping {cancer_name} - not enough mutated samples having RPPA data')
                # print(samples_with_muts_present)
                pass
            continue
        else:
            print(f'Using {samples_with_muts_present} for {cancer_name}')

        samples_without_muts = rppa_samples - samples_with_muts_present

        results = {}
        for antibody, data in cancer_rppa.iterrows():
            if antibodies and not any(a in antibodies for a in antibody.split(' ')):
                continue
            rppa_carriers = [
                expression_distributions[sample](data[sample])
                for sample in samples_with_muts_present
                if not isnan(data[sample])
            ]
            if len(rppa_carriers) < threshold:
                if verbose and antibody == 'MET':
                    print(f'Skipping {gene}/{cancer_name}/{antibody} - not enough mutated samples having RPPA data != nan')
                continue
            if antibody == 'MET':
                print(rppa_carriers)

            rppa_non_carriers = [
                expression_distributions[sample](data[sample])
                for sample in samples_without_muts
                if not isnan(data[sample])
            ]
            if cancer_name == 'Skin Cutaneous Melanoma':
                #print(antibody, cancer_name, 'mean_difference', mean(rppa_carriers) - mean(rppa_non_carriers))
                pass

            result = wilcox(FloatVector(rppa_carriers), FloatVector(rppa_non_carriers))
            p = result.rx("p.value")[0][0]
            results[antibody] = {
                'p_value': p,
                'wilcox_statistic': result.rx('statistic')[0][0],
                'mean_difference': mean(rppa_carriers) - mean(rppa_non_carriers),
                'mean_non_carrier': mean(rppa_non_carriers),
                'mean_carrier': mean(rppa_carriers)
            }
            if verbose and antibody == 'MET':
                print(antibody, results[antibody])

        p_values = [r['p_value'] for r in results.values()]
        p_adjusted = stats.p_adjust(FloatVector(p_values), method='BH')
        for v, fdr, p in zip(results.values(), p_adjusted, p_values):
            assert p == v['p_value'] or isnan(p)
            v['fdr'] = fdr

        for antibody, result in results.items():

            if result['p_value'] < 0.05:
                c += 1
                d.add(antibody)
            if result['fdr'] < 0.15:
                print(f'Hit among {len(results)}')
                print(cancer_name, antibody, result)
                suggestive_or_significant.append((cancer_name, gene, antibody, result))
            testable_genes.add(gene)
    print(c, len(d))
    return suggestive_or_significant, testable_genes


def scan_active_driver_genes(modification_type, pan_cancer=True, limit_to_protein_itself=False):
    if pan_cancer:
        results = pan_cancer_analysis(modification_type)
        all_results = {None: results}
        cancer_names = {None: None}
    else:
        all_results = per_cancer_analysis(modification_type)

        cancer_names = {
            cancer.code: cancer.name
            for cancer in Cancer.query
        }

    if limit_to_protein_itself:
        rppa = load_rppa()
        tested_genes = set()

    significant_genes = set()
    genes_with_enough_samples = set()

    for cancer_code, results in all_results.items():
        top = results['top_fdr']
        cancer_name = cancer_names[cancer_code]
        for gene in top.gene:
            print(f'Checking {gene} in "{cancer_name}"')
            if limit_to_protein_itself:
                if gene in rppa.index:
                    antibodies = [gene]
                    tested_genes.add(gene)
                else:
                    continue
            else:
                antibodies = None
            hits, tested_genes = differential_expression_ptm_muts(gene, modification_type, cancer_name=cancer_name, antibodies=antibodies)
            genes_with_enough_samples.update(tested_genes)
            significant_genes.update({r[1] for r in hits})

    if limit_to_protein_itself:
        print(f'Tested genes: {len(tested_genes)}')
    print(f'Gene with significant hits: {significant_genes}')
    print(f'Testable genes {genes_with_enough_samples}')
