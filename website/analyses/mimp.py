import shutil
from pathlib import Path
from random import sample
from typing import Set, NamedTuple, List
from warnings import warn
from collections import Counter

from pandas import Series, to_numeric
from rpy2.robjects import pandas2ri, StrVector, ListVector, r
from rpy2.robjects.packages import importr
from tqdm import tqdm

from analyses.active_driver import prepare_active_driver_data
from models import Kinase, Site, SiteType, Protein, extract_padded_sequence


pandas2ri.activate()


def load_mimp():
    return importr("rmimp")


def save_kinase_sequences(kinase, sequences, seq_dir):

    if not sequences:
        warn(
            f'No sequences for {kinase.name} created in {seq_dir},'
            f' as no sequences were found.'
        )

    with open(seq_dir / f'{kinase.name}.sequences', 'w') as f:
        f.write(kinase.name + '\n')
        for sequence in sequences:
            f.write(sequence + '\n')


class NegativeSite(NamedTuple):
    protein: Protein
    position: int


def gather_negative_sites(residues: Set[str], exclude: Set[Site]) -> Set[NegativeSite]:
    """
    Gather sites for negative sequences which will be centered on
    residues from `residues` set, from the proteome exclusive of
    sites provided in `exclude` set.
    """

    candidate_negative_sites: Set[NegativeSite] = set()

    preferred_isoforms = Protein.query.filter(Protein.is_preferred_isoform)

    for protein in tqdm(preferred_isoforms, total=preferred_isoforms.count()):

        positions_to_skip = {
            site.position - 1   # convert to 0-based
            for site in protein.sites
            if site in exclude
        }

        for i, aa in enumerate(protein.sequence):
            if i in positions_to_skip:
                continue
            if aa in residues:
                candidate_negative_sites.add(
                    NegativeSite(protein, i)
                )

    return candidate_negative_sites


def sample_random_negative_sequences(negative_sites: Set[NegativeSite], n=10000) -> List[str]:
    """Sample `n` negative sequences from set of negative sites."""
    if n > len(negative_sites):
        warn(f'n = {n} is greater then len(negative_sites) = {len(negative_sites)}')

    random_sites = sample(negative_sites, n)

    random_sequences = [
        # here site.position is 0-based
        extract_padded_sequence(
            site.protein,
            site.position - 7,
            site.position + 7 + 1
        )
        for site in random_sites
    ]

    return random_sequences


def calculate_background_frequency():
    """Calculates background frequency of aminoacids (priors) for MIMP."""
    counts = Counter()
    total_length = 0

    preferred_isoforms = Protein.query.filter(Protein.is_preferred_isoform)

    for protein in tqdm(preferred_isoforms, total=preferred_isoforms.count()):
        for aa in protein.sequence:
            if aa == '*':
                continue
            counts[aa] += 1
            total_length += 1

    for aa, count in counts.items():
        counts[aa] = count / total_length

    return counts


def train_model(site_type: SiteType, sequences_dir='.tmp', sampling_n=10000, output_path=None, **kwargs):
    """Train MIMP model for given site type.

    NOTE: Natively MIMP works on phosphorylation sites only,
    so a special, forked version [reimandlab/rmimp] is needed
    for this function to work at all.

    Args:
        site_type: Type of the site for which the model is to be trained
        sequences_dir: path to dir where sequences for trainModel should be dumped
        sampling_n: number of sampling iterations for negative sequence set
        output_path: path to .mimp file where the model should be saved
        **kwargs: will be passed to trainModel

    Returns:
        trained MIMP model for all kinases affecting sites of given SiteType
    """
    if not output_path:
        output_path = f'{site_type.name}.mimp'

    mimp = load_mimp()

    sites_of_this_type = set(site_type.sites)
    modified_residues = site_type.find_modified_residues()

    negative_sites = gather_negative_sites(modified_residues, exclude=sites_of_this_type)

    sequences_path = Path(sequences_dir)

    positive_path = sequences_path / 'positive'
    negative_path = sequences_path / 'negative'

    for path in [positive_path, negative_path]:
        shutil.rmtree(str(path), ignore_errors=True)
        path.mkdir(parents=True)

    kinases = Kinase.query.filter(
        Kinase.sites.any(Site.type.contains(site_type))
    )

    for kinase in tqdm(kinases, total=kinases.count()):

        sites = [
            site
            for site in kinase.sites
            if site_type.name in site.type
        ]

        positive_sequences = [site.sequence for site in sites]
        negative_sequences = sample_random_negative_sequences(negative_sites, sampling_n)

        save_kinase_sequences(kinase, positive_sequences, positive_path)
        save_kinase_sequences(kinase, negative_sequences, negative_path)

    priors = mimp.PRIORS.rx2('human')

    # just in case
    # r.debug(mimp.trainModel)

    return mimp.trainModel(
        str(positive_path), str(negative_path),
        file=output_path,
        priors=priors,    # or calculate_background_frequency(),
        # both give the same values (within rounding error), the custom
        # func might come in handy in future
        # TODO: how to group the residues? some site-type specific mapping is needed here
        # TODO: as well as some literature review
        residues_groups=StrVector(['|'.join(modified_residues)]),
        **kwargs
    )


def run_mimp(mutation_source: str, site_type: str, model: str=None):
    """Run MIMP for given source of mutations and given site type.

    Args:
        mutation_source: name of mutation source
        site_type: name of site type
        model: name of the model or path to custom .mimp file,
               if not specified, an automatically generated,
               custom, site-based model will be used.
    """

    if not model:
        path = Path(site_type + '.mimp')
        if path.exists():
            print(f'Reusing existing custom MIMP model: {path}')
        else:
            model = train_model(SiteType(name=site_type), output_path=str(path))
            if not model:
                raise Exception('Running MIMP not possible: trained model is empty')
            assert path.exists()
        model = str(path)

    mimp = load_mimp()

    sequences, disorder, mutations, sites = prepare_active_driver_data(
        mutation_source, site_type
    )

    mutations = mutations.assign(mutation=Series(
        m.wt_residue + str(m.position) + m.mut_residue
        for m in mutations.itertuples(index=False)
    ).values)

    sites.position = to_numeric(sites.position)
    sequences = ListVector(sequences)

    return mimp.site_mimp(
        mutations[['gene', 'mutation']], sequences,
        site_type=site_type, sites=sites[['gene', 'position']],
        **{'model.data': model}
    )
