from functools import partial
from itertools import chain
from pathlib import Path
from subprocess import Popen
from tempfile import NamedTemporaryFile
from typing import List

from analyses import active_driver
from analyses.active_driver import ActiveDriverResult


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
    cmd = [python_path, str(working_dir / f'{module_name}.py'), *args] + [
        arg
        for arg in chain(*[
            [key_prefix + key] + (value if isinstance(value, list) else [str(value)])
            for key, value in kwargs.items()
        ])
    ]
    return cmd


def run_python(*args, **kwargs):
    return Popen(python(*args, **kwargs)).wait()


def create_network_files(hotnet, networks_dir, networks, num_network_permutations=100, num_cores=-1):

    for name, beta in networks.items():
        hotnet(
            'makeNetworkFiles',
            edgelist_file=f'{networks_dir}/{name}/{name}_edge_list',
            gene_index_file=f'{networks_dir}/{name}/{name}_index_gene',
            network_name=name,
            prefix=name,
            beta=beta,
            output_dir=f'{networks_dir}/{name}',
            num_permutations=num_network_permutations,
            cores=num_cores
        )


def run_on_active_driver_results(
    active_driver_results: ActiveDriverResult, hotnet_path, interpreter='python',
    num_heat_permutations=1000, num_network_permutations=100, num_cores=-1
):
    hotnet_path = Path(hotnet_path)

    networks_dir = hotnet_path / 'paper/data/networks'

    networks = {
        'hint+hi2012': 0.4,
        'irefindex9': 0.45,
        'multinet': 0.5
    }

    hotnet = partial(run_python, python_path=interpreter, working_dir=hotnet_path)

    if any(
        not (networks_dir / f'{name}/{name}_ppr_{beta}.h5').exists()
        for name, beta in networks.items()
    ):
        print('Creating network files...')
        create_network_files(hotnet, networks_dir, networks, num_network_permutations, num_cores)

    df = active_driver_results['all_gene_based_fdr']
    df = df.set_index('gene')['p']

    with NamedTemporaryFile('w') as input_heat_file, NamedTemporaryFile('w') as output_heat_file:

        # generate initial heat (genes/nodes value = p-values from AD)
        df.to_csv(input_heat_file.name, sep='\t')

        # convert the heat file into HotNet json file
        results = hotnet(
            'makeHeatFile',
            'scores',
            heat_file=input_heat_file.name,
            output_file=output_heat_file.name
        )

        # run HotNet
        hotnet(
            'HotNet2',
            network_files=[
                f'{networks_dir}/{name}/{name}_ppr_{beta}.h5'
                for name, beta in networks.items()
            ],
            permuted_network_paths=[
                f'{networks_dir}/{name}/permuted/{name}_ppr_{beta}_##NUM##.h5'
                for name, beta in networks.items()
            ],
            heat_files=output_heat_file.name,
            network_permutations=num_network_permutations,
            heat_permutations=num_heat_permutations,
            output_directory='analyses_results/hotnet2',
            num_cores=num_cores
        )


def run_all(site_type: str, **kwargs):

    for analysis in [active_driver.pan_cancer_analysis, active_driver.clinvar_analysis]:
        result = analysis(site_type)
        run_on_active_driver_results(result, **kwargs)
