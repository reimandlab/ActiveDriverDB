from functools import partial
from itertools import chain
from pathlib import Path
from subprocess import check_output
from tempfile import NamedTemporaryFile
from typing import List
from collections import defaultdict, Counter

from pandas import read_table, Series
import numpy as np
from tqdm import tqdm

from analyses import active_driver
from analyses.active_driver import ActiveDriverResult
from database import db
from models import Pathway, Gene


OUTPUT_DIR = Path('analyses_output/hotnet2')


def python(module_name, *args, python_path='python', working_dir=Path('.'), key_prefix='--', **kwargs) -> List:
    """Create args list for execution of python as a subprocess in Popen.

    Args:
        module_name: name of the python script
        *args: subparser selection
        python_path: path to the python interpreter, e.g. in a virtual environment
        working_dir: path to the directory with the module
        key_prefix: '-' for short args, '--' for long format
        **kwargs: arguments to be passed to parser or subparser
    """
    cmd = [str(python_path), str(working_dir / f'{module_name}.py'), *args] + [
        arg
        for arg in chain(*[
            [key_prefix + key] + (value if isinstance(value, list) else [str(value)])
            for key, value in kwargs.items()
        ])
    ]
    return cmd


def run_python(*args, **kwargs):
    cmd = python(*args, **kwargs)
    return check_output(cmd)


class HotNet:

    def __init__(self, interpreter, path):
        path = Path(path).absolute()
        self.networks_dir = path / 'paper/data/networks'
        self.command = partial(run_python, python_path=interpreter, working_dir=path)

    def edge_list(self, name):
        return self.networks_dir / f'{name}/{name}_edge_list'

    def gene_list(self, name):
        return self.networks_dir / f'{name}/{name}_index_gene'

    def beta_file(self, name):
        return self.networks_dir / f'{name}/{name}_beta'

    def permutations_file(self, name, beta):
        return self.networks_dir / f'{name}/{name}_ppr_{beta}.h5'

    def create_network_files(self, networks, num_network_permutations=100, num_cores=-1):

        for name, beta in networks.items():
            self.command(
                'makeNetworkFiles',
                edgelist_file=self.edge_list(name),
                gene_index_file=self.gene_list(name),
                network_name=name,
                prefix=name,
                beta=beta,
                output_dir=f'{self.networks_dir}/{name}',
                num_permutations=num_network_permutations,
                cores=num_cores
            )

    def create_network(self, name, data_path, filter_by_gmt_pathways=True):
        network_dir = self.networks_dir / name
        network_dir.mkdir(exist_ok=True)

        network = read_table(data_path)

        if filter_by_gmt_pathways:
            all_genes_in_pathways = {name for name, in db.session.query(Gene.name).join(Pathway.genes)}
            network = network.ix[
                [
                    edge.Index
                    for edge in network.itertuples()
                    if edge.protein1 in all_genes_in_pathways and edge.protein2 in all_genes_in_pathways
                ]
            ]

        with NamedTemporaryFile('w') as network_file:

            network[['protein1', 'protein2']].to_csv(network_file, sep='\t', index=False)

            self.command(
                'scripts/createNetwork',
                network_file=network_file.name,
                edgelist_file=self.edge_list(name),
                gene_index_file=self.gene_list(name),
            )

        beta_file = self.beta_file(name)
        self.command(
            'scripts/chooseBeta',
            edge_list_file=self.edge_list(name),
            output_file=beta_file
        )

        return beta_file


HOTNET_PUBLICATION_NETWORKS = {
    'hint+hi2012': 0.4,
    'irefindex9': 0.45,
    'multinet': 0.5,
}


def run_on_active_driver_results(
    active_driver_results: ActiveDriverResult, analysis_name, hotnet_path,
    interpreter='python', networks=HOTNET_PUBLICATION_NETWORKS,
    num_heat_permutations=1000, num_network_permutations=100, num_cores=-1,
    score_by='p'
):
    """
    Args:
        score_by: what to use for scoring: 'p' for p-value, 'fdr' for q-value
    """
    hotnet_path = Path(hotnet_path)
    interpreter = Path(interpreter)
    analysis_name += '_' + score_by
    output_dir = OUTPUT_DIR / analysis_name

    hotnet = HotNet(interpreter, hotnet_path)

    if any(
        not hotnet.permutations_file(name, beta).exists()
        for name, beta in networks.items()
    ):
        print('Creating network files...')
        hotnet.create_network_files(networks, num_network_permutations, num_cores)

    df = active_driver_results['all_gene_based_fdr']
    df[score_by] = - np.log10(df[score_by])
    df = df.set_index('gene')[score_by]

    with NamedTemporaryFile('w') as input_heat_file, NamedTemporaryFile('w', suffix='.json') as output_heat_file:

        # generate initial heat (genes/nodes value = p-values from AD)
        df.to_csv(input_heat_file.name, sep='\t', header=False)

        # convert the heat file into HotNet json file
        results = hotnet.command(
            'makeHeatFile',
            'scores',
            heat_file=input_heat_file.name,
            output_file=output_heat_file.name,
            name=analysis_name
        )

        # run HotNet
        hotnet.command(
            'HotNet2',
            network_files=[
                f'{hotnet.networks_dir}/{name}/{name}_ppr_{beta}.h5'
                for name, beta in networks.items()
            ],
            permuted_network_paths=[
                f'{hotnet.networks_dir}/{name}/permuted/{name}_ppr_{beta}_##NUM##.h5'
                for name, beta in networks.items()
            ],
            heat_files=output_heat_file.name,
            network_permutations=num_network_permutations,
            heat_permutations=num_heat_permutations,
            output_directory=output_dir,
            num_cores=num_cores
        )
        print(f'HotNet2 is ready. The results are saved in {output_dir}. Use:')
        print(f'cd {hotnet_path}/viz')
        print('# To install required dependencies - needed just once: ')
        print(f'{interpreter.absolute()} -m pip install -r requirements.txt')
        print('sudo npm install -g bower')
        print('bower install')
        print('# To run vizualization server:')
        print(f'{interpreter.absolute()} server.py -i {output_dir.absolute()}')


def export_both(site_type, score_by='p', mode='max'):

    analyses = [active_driver.pan_cancer_analysis, active_driver.clinvar_analysis]
    scores = []

    for analysis in analyses:
        result = analysis(site_type)
        df = result['all_gene_based_fdr']
        df[score_by] = - np.log10(df[score_by])
        df = df.set_index('gene')[score_by]
        scores.append(df)

    cancer = scores[0]
    clinvar = scores[1]

    if mode == 'product':
        combined_scores = cancer * clinvar
        combined_scores = combined_scores.fillna(0)
    elif mode == 'max':
        all_genes = set(list(cancer.index) + list(clinvar.index))
        cancer = Series({gene: cancer.get(gene, 0) for gene in all_genes})
        clinvar = Series({gene: clinvar.get(gene, 0) for gene in all_genes})
        combined_scores = cancer.where(cancer > clinvar, clinvar).fillna(cancer)
    else:
        raise ValueError(f'Wrong mode: {mode}')

    combined_scores.to_csv('hotnet_input_heat_combined', sep='\t', header=False)


def run_all(site_type: str, **kwargs):

    for analysis in [active_driver.pan_cancer_analysis, active_driver.clinvar_analysis]:
        result = analysis(site_type)
        run_on_active_driver_results(result, analysis.name + '_' + site_type, **kwargs)


def run_all_from_biogrid(site_type: str, hotnet_path, interpreter, **kwargs):
    hot_net = HotNet(interpreter, hotnet_path)

    beta_file = hot_net.beta_file('biogrid_hc')

    if not beta_file.exists():
        hot_net.create_network('biogrid_hc', 'data/networks/PPI_network_BioGrid_HC.txt')

    with open(beta_file) as f:
        beta = float(f.read().strip())

    run_all(
        site_type, interpreter=interpreter, hotnet_path=hotnet_path,
        networks={'biogrid_hc': beta}, **kwargs
    )


def visualize_subnetwork(gene_names, source='MC3', site_type_name='glycosylation', mode='samples with'):
    import seaborn as sns
    import matplotlib.pyplot as plt

    from pandas import DataFrame

    assert mode in ('samples with', 'unique')

    mutations_by_cancer = defaultdict(Counter)  # cancer_code: mutations_count_by_site_protein_and_position
    for gene_name in tqdm(gene_names):
        gene = Gene.query.filter_by(name=gene_name).one()
        protein = gene.preferred_isoform
        muts = [m for m in protein.mutations if 'MC3' in m.sources]
        codes = set()

        for mut in muts:
            count = 1 if mode == 'unique' else mut.meta_MC3.get_value()

            for site in mut.affected_sites:
                if any(site_type_name in site_type.name for site_type in site.types):
                    site_name = f'{gene_name} {site.position}{site.residue}'
                    codes = mut.mc3_cancer_code
                    for code in codes:
                        mutations_by_cancer[code][site_name] += count

    data = DataFrame(mutations_by_cancer)

    fig, ax = plt.subplots(figsize=(10, 12))
    ax.tick_params(axis='both', which='both', length=0)
    plot = sns.heatmap(
        data, cmap='RdYlGn_r', linewidths=0.5, annot=True, ax=ax,
        cbar_kws={"shrink": 0.5, 'label': f'Count of {mode} mutations affecting {site_type_name} sites'}
    )

    fig = plot.get_figure()
    fig.tight_layout()
    fig.savefig('Subnetwork of: ' + ','.join(gene_names) + '.svg')

    return data
