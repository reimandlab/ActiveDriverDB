from functools import lru_cache
from pathlib import Path

from pandas import DataFrame
from rpy2.robjects import pandas2ri, r, NULL as null, StrVector
from rpy2.robjects.packages import importr
from tqdm import tqdm

from analyses import active_driver
from analyses.active_driver import ActiveDriverResult
from models import InterproDomain

pandas2ri.activate()

output_dir = Path('analyses_output/active_pathway/')

sets_path = Path('data/gene_sets/')


@lru_cache()
def gmt_from_domains(path=sets_path / 'domains.gmt', include_sub_types=True):
    """Export sets of genes having the same domains into a GMT file"""
    with open(path, 'w') as f:

        query = InterproDomain.query
        for domain_type in tqdm(query, total=query.count()):

            # collect all occurrences
            occurrences = []
            occurrences.extend(domain_type.occurrences)

            if include_sub_types:
                sub_types = domain_type.children[:]
                while sub_types:
                    sub_type = sub_types.pop()
                    occurrences.extend(sub_type.occurrences)
                    sub_types.extend(sub_type.children)

            line = [
                domain_type.accession,
                domain_type.description,
                *{domain.protein.gene_name for domain in occurrences}
            ]

            f.write('\t'.join(line) + '\n')

    return path


gene_sets = {
    # GMT files downloaded from Broad Institute:
    # these files has to be manually downloaded from
    # http://software.broadinstitute.org/gsea/msigdb/collections.jsp
    'hallmarks': sets_path / 'h.all.v6.1.symbols.gmt',
    'all_canonical_pathways': sets_path / 'c2.cp.reactome.v6.1.symbols.gmt',
    'gene_ontology': sets_path / 'c5.all.v6.1.symbols.gmt',
    'oncogenic': sets_path / 'c6.all.v6.1.symbols.gmt',
    'immunologic': sets_path / 'c7.all.v6.1.symbols.gmt',
    # other gene sets
    'human_pathways': 'data/hsapiens.pathways.NAME.gmt',
    'drug_targets': sets_path / 'Human_DrugBank_all_symbol.gmt',
    'domains': gmt_from_domains
}


def run_active_pathways(ad_result: ActiveDriverResult, gene_sets_gmt_path: str, cytoscape_dir: Path=None) -> DataFrame:
    active_pathways = importr('activeDriverPW')
    df = ad_result['all_gene_based_fdr']
    df = df.set_index('gene')['fdr']
    scores = r['as.matrix'](df)

    cytoscape_paths = StrVector([
        str(cytoscape_dir / name)
        for name in ['terms.txt', 'groups.txt', 'abridged.gmt']
    ]) if cytoscape_dir else null

    return active_pathways.activeDriverPW(scores, gene_sets_gmt_path, cytoscape_filenames=cytoscape_paths)


def run_all(site_type):
    """Runs all active_pathways combinations for given site_type.

    Uses pan_cancer/clinvar Active Driver analyses results
    and all GMT gene sets from Broad Institute.

    Results are saved in `output_dir`.
    """
    data_table = importr('data.table')

    for analysis in [active_driver.pan_cancer_analysis, active_driver.clinvar_analysis]:
        for gene_set in gene_sets:
            path = output_dir / analysis.name / gene_set / site_type
            path.mkdir(parents=True, exist_ok=True)

            ad_result = analysis(site_type)
            print(f'Preparing active pathways: {analysis.name} for {len(ad_result["all_gene_based_fdr"])} genes')
            print(f'Gene sets/background: {gene_set}')

            gene_sets_path = gene_sets[gene_set]

            if callable(gene_sets_path):
                gene_sets_path = gene_sets_path()

            result = run_active_pathways(ad_result, str(gene_sets_path), cytoscape_dir=path)

            data_table.fwrite(result, str(path / 'pathways.tsv'), sep='\t', sep2=r.c('', ',', ''))
