import signal
from contextlib import ExitStack
from functools import lru_cache
from pathlib import Path
from shutil import rmtree
from subprocess import Popen
from tempfile import NamedTemporaryFile

import os
from typing import Mapping, Tuple

from pandas import DataFrame
from rpy2.robjects import pandas2ri, r, NULL as null, StrVector, IntVector
from rpy2.robjects.packages import importr
from tqdm import tqdm

from analyses import active_driver
from analyses.active_driver import ActiveDriverResult
from helpers.cytoscape import CytoscapeCommand, Cytoscape, get
from models import InterproDomain

#pandas2ri.activate()

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


GENE_SETS = {
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


def run_active_pathways(
    ad_result: ActiveDriverResult, gene_sets_gmt_path: str,
    cytoscape_dir: Path=None, **kwargs
) -> DataFrame:
    active_pathways = importr('activeDriverPW')
    df = ad_result['all_gene_based_fdr']
    df = df.set_index('gene')['p']
    scores = r['as.matrix'](df)

    cytoscape_paths = StrVector([
        str(cytoscape_dir / name)
        for name in ['terms.txt', 'groups.txt', 'abridged.gmt']
    ]) if cytoscape_dir else null

    return active_pathways.activeDriverPW(scores, gene_sets_gmt_path, cytoscape_filenames=cytoscape_paths, **kwargs)


class EnrichmentMap(CytoscapeCommand):
    """API for initial processing and loading of enrichment maps in Cytoscape"""

    build = get(defaults={'analysisType': 'generic'}, plain_text=True)


class DeadlyPopen(Popen):
    """Same as Popen, but commits suicide on exit"""

    def __init__(self, *args, kill_descendants=True, **kwargs):
        self.kill_descendants = kill_descendants
        if kill_descendants:
            kwargs['preexec_fn'] = os.setsid
        super().__init__(*args, **kwargs)

    def __exit__(self, *args, **kwargs):
        if self.kill_descendants:
            os.killpg(self.pid, signal.SIGKILL)
        else:
            self.terminate()
            self.kill()


def run_all(site_type: str, gene_sets: Mapping[str, Path]=GENE_SETS, gene_set_filter: Tuple[int]=(5, 1000), correct=False, **kwargs):
    """Runs all active_pathways combinations for given site_type.

    Uses pan_cancer/clinvar Active Driver analyses results
    and all provided GMT gene sets.

    Args:
        site_type: site filter which will be passed to ActiveDriver analysis
        gene_sets: gene sets to be considered
        gene_set_filter: a two-tuple: (min, max) number of genes required
            to be in a gene set. If not set, the default of (5, 1000) is used

    Results are saved in `output_dir`.

    Returns:
        Mapping of directories with newly computed ActivePathways results
    """
    data_table = importr('data.table')
    paths = {}

    kwargs['geneset.filter'] = IntVector(gene_set_filter)

    for analysis in [active_driver.pan_cancer_analysis, active_driver.clinvar_analysis]:
        for gene_set in gene_sets:
            path = output_dir / analysis.name / gene_set / site_type

            # remove the old results (if any)
            rmtree(path, ignore_errors=True)
            # recreate dir
            path.mkdir(parents=True)

            path = path.absolute()

            ad_result = analysis(site_type)
            print(f'Preparing active pathways: {analysis.name} for {len(ad_result["all_gene_based_fdr"])} genes')
            print(f'Gene sets/background: {gene_set}')

            gene_sets_path = gene_sets[gene_set]

            if callable(gene_sets_path):
                gene_sets_path = gene_sets_path()

            result = run_active_pathways(ad_result, str(gene_sets_path), cytoscape_dir=path, correct=correct, **kwargs)

            data_table.fwrite(result, str(path / 'pathways.tsv'), sep='\t', sep2=r.c('', ',', ''))

            paths[(analysis, gene_set)] = path

    return paths


def generate_enrichment_maps(paths, cytoscape_path):
    """Generate Cytoscape
    `cytoscape_path` should point to a dir with 'cytoscape.sh' script in it.
    """

    with ExitStack() as stack:
        cytoscape_server_path = Path(cytoscape_path) / 'cytoscape.sh'

        # start cytoscape REST API server in a context manager
        # (so it will be close automatically upon exit or error)
        port = 1234
        cytoscape_out = stack.enter_context(NamedTemporaryFile())
        print('Starting Cytoscape...')
        print(f'All the output will be saved in {cytoscape_out.name}')

        stack.enter_context(
            DeadlyPopen(
                [cytoscape_server_path, '-R', str(port)],
                kill_descendants=True,
                stdout=cytoscape_out
            )
        )
        cytoscape = Cytoscape()

        enrichment_app = EnrichmentMap(port=port)

        for (analysis, gene_set), path in paths.items():

            enrichment_path = str(path / 'terms.txt')
            gmt_path = path / 'abridged.gmt'
            if gmt_path.exists():
                response = enrichment_app.build(gmtFile=str(gmt_path), enrichmentsDataset1=enrichment_path)
                print('Cytoscape Enrichment Map:', response)

                cytoscape.session.save_as(data={'file': str(path / 'enrichment_map.cys')})
                cytoscape.session.new()
            else:
                print(f'No gmt file for {analysis.name} & {gene_set} - no cytoscape network will be created')
