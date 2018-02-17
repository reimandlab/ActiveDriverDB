from pathlib import Path

from pandas import DataFrame
from rpy2.robjects import pandas2ri, r, NULL as null, StrVector
from rpy2.robjects.packages import importr

from analyses import active_driver
from analyses.active_driver import ActiveDriverResult

pandas2ri.activate()

output_dir = Path('analyses_output/active_pathway/')

bi_path = Path('data/gene_sets/')

# GMT files downloaded from Broad Institute:
# these files has to be manually downloaded from
# http://software.broadinstitute.org/gsea/msigdb/collections.jsp
bi_gene_sets = {
    'hallmarks': 'h.all.v6.1.symbols.gmt',
    'gene_ontology': 'c5.all.v6.1.symbols.gmt',
    'oncogenic': 'c6.all.v6.1.symbols.gmt',
    'immunologic': 'c7.all.v6.1.symbols.gmt',
}


def run_active_pathways(ad_result: ActiveDriverResult, gene_sets_gmt_path: str, cytoscape_dir: Path=None) -> DataFrame:
    active_pathways = importr('activeDriverPW')
    df = ad_result['all_gene_based_fdr']
    df = df.set_index('gene')['p']
    scores = r['as.matrix'](df)

    cytoscape_paths = StrVector([
        str(cytoscape_dir / name)
        for name in ['terms.txt', 'groups.txt', 'abridged.gmt']
    ]) if cytoscape_dir else null

    return active_pathways.activeDriverPW(scores, gene_sets_gmt_path, cytoscape_filenames=cytoscape_paths)


def active_pathways_from_bi(ad_result: ActiveDriverResult, gene_set_name: str, cytoscape_dir: Path=None) -> DataFrame:
    gene_sets_path = bi_path / bi_gene_sets[gene_set_name]
    return run_active_pathways(ad_result, str(gene_sets_path), cytoscape_dir)


def run_all(site_type):
    """Runs all active_pathways combinations for given site_type.

    Uses pan_cancer/clinvar Active Driver analyses results
    and all GMT gene sets from Broad Institute.

    Results are saved in `output_dir`.
    """
    data_table = importr('data.table')

    for analysis in [active_driver.pan_cancer_analysis, active_driver.clinvar_analysis]:
        for bi_set in bi_gene_sets:
            path = output_dir / analysis.name / bi_set / site_type
            path.mkdir(parents=True, exist_ok=True)

            ad_result = analysis(site_type)
            result = active_pathways_from_bi(ad_result, bi_set, cytoscape_dir=path)

            data_table.fwrite(result, str(path / 'pathways.tsv'), sep='\t', sep2=r.c('', ',', ''))
