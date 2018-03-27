import shutil
from pathlib import Path
from random import sample
from types import SimpleNamespace
from typing import Set, NamedTuple, List
from warnings import warn
from collections import Counter, defaultdict

from pandas import Series, to_numeric, DataFrame
from rpy2.robjects import pandas2ri, StrVector, ListVector, r
from rpy2.robjects.constants import NULL
from rpy2.robjects.packages import importr
from tqdm import tqdm

from analyses.active_driver import prepare_active_driver_data
from helpers.plots import sequence_logo
from models import Kinase, Site, SiteType, Protein, extract_padded_sequence

from ._paths import ANALYSES_OUTPUT_PATH


pandas2ri.activate()
r("options(warn=1)")


def load_mimp():
    return importr("rmimp")


def save_kinase_sequences(kinase, sequences, seq_dir):

    if not sequences:
        warn(
            f'No sequences for {kinase.name} created in {seq_dir},'
            f' as no sequences were found.'
        )

    # make it possible to use BCR/ABL as filename
    name = kinase.name.replace('/', '-')

    with open(seq_dir / f'{name}.sequences', 'w') as f:
        f.write(name + '\n')
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


def residues_groups(site_type, modified_residues):
    if site_type.name == 'phosphorylation':
        return StrVector(['S|T', 'Y'])
    # TODO: better grouping residues for site-specific enzymes:
    # for glycosylation there are ~16 enzymes; the idea would be
    # to load "site" : "terminal sugar" associations (e.g. from O-GlycBase)
    # and then map "terminal sugar" : "enzyme" for enzymes known to catalyze
    # glycosylation with given "terminal sugar" (& fro given link type)
    # Some additional literature review might be needed
    return StrVector(['|'.join(modified_residues)])


def train_model(site_type: SiteType, sequences_dir='.tmp', sampling_n=10000, enzyme_type='kinase', output_path=None, **kwargs):
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

    if enzyme_type == 'kinase':

        enzymes = Kinase.query.filter(
            Kinase.is_involved_in.any(SiteType.name == site_type.name)
        ).filter(
            Kinase.sites.any(Site.types.contains(site_type))
        )
        enzymes = tqdm(enzymes, total=enzymes.count())

    elif enzyme_type == 'catch-all':
        enzymes = [
            SimpleNamespace(
                sites=Site.query.filter(Site.types.contains(site_type)),
                name=f'all_enzymes_for_{site_type.name}'
            )
        ]
    else:
        assert False

    for enzyme in enzymes:

        sites = [
            site
            for site in enzyme.sites
            if site_type in site.types
        ]

        positive_sequences = [site.sequence for site in sites]
        negative_sequences = sample_random_negative_sequences(negative_sites, sampling_n)

        save_kinase_sequences(enzyme, positive_sequences, positive_path)
        save_kinase_sequences(enzyme, negative_sequences, negative_path)

    priors = mimp.PRIORS.rx2('human')

    # just in case
    # r.debug(mimp.trainModel)

    return mimp.trainModel(
        str(positive_path), str(negative_path),
        file=output_path,
        priors=priors,    # or calculate_background_frequency(),
        # both give the same values (within rounding error), the custom
        # func might come in handy in future
        residues_groups=residues_groups(site_type, modified_residues),
        **kwargs
    )


class EmptyModel(Exception):
    pass


def get_or_create_model_path(site_type: SiteType, enzyme_type) -> str:
    path = Path(site_type.name + '.mimp')
    if path.exists():
        print(f'Reusing existing custom MIMP model: {path}')
    else:
        model = train_model(site_type, output_path=str(path), enzyme_type=enzyme_type)
        if not model:
            raise EmptyModel('Running MIMP not possible: the trained model is empty')
        assert path.exists()
    return str(path)


def run_mimp(mutation_source: str, site_type_name: str, model: str=None, enzyme_type='kinase') -> DataFrame:
    """Run MIMP for given source of mutations and given site type.

    Args:
        mutation_source: name of mutation source
        site_type_name: name of site type
        model: name of the model or path to custom .mimp file,
            if not specified, an automatically generated,
            custom, site-based model will be used.
        enzyme_type: is the enzyme that modifies the site a kinase?
            if not use "catch-all" strategy: train MIMP as if there
            was just one site-specific enzyme - just because we do
            not have information about enzyme-site specificity for
            enzymes other than kinases (yet!)
    """
    site_type = SiteType.query.filter_by(name=site_type_name).one()

    if not model:
        model = get_or_create_model_path(site_type, enzyme_type)

    mimp = load_mimp()

    sequences, disorder, mutations, sites = prepare_active_driver_data(
        mutation_source, site_type_name
    )

    mutations = mutations.assign(mutation=Series(
        m.wt_residue + str(m.position) + m.mut_residue
        for m in mutations.itertuples(index=False)
    ).values)

    sites.position = to_numeric(sites.position)

    sequences = ListVector(sequences)

    modified_residues = site_type.find_modified_residues()

    mimp_result = mimp.site_mimp(
        mutations[['gene', 'mutation']], sequences,
        site_type=site_type_name, sites=sites[['gene', 'position']],
        residues_groups=residues_groups(site_type, modified_residues),
        **{'model.data': model}
    )
    if mimp_result is NULL:
        return DataFrame()
    return pandas2ri.ri2py(mimp_result)


glycosylation_sub_types = [
    'N-glycosylation',
    'O-glycosylation',
    'C-glycosylation',
    'S-glycosylation',
]


def iterate_mimp_models(site_types, enzyme_type):

    for site_type_name in site_types:
        site_type = SiteType.query.filter_by(name=site_type_name).one()

        try:
            model_path = get_or_create_model_path(site_type, enzyme_type=enzyme_type)
        except EmptyModel as e:
            print(e)
            continue

        models = r.readRDS(model_path)

        for model in models:
            pwm = model.rx2('pwm')
            name = model.rx2('name')[0]

            yield name, pwm, site_type


def sequence_logos_for_site_types(site_types, enzyme_type='kinase'):
    logos_path = ANALYSES_OUTPUT_PATH / 'mimp' / 'logos'

    logos = defaultdict(dict)

    for model_name, pwm, site_type in iterate_mimp_models(site_types, enzyme_type):

        site_logos_path = logos_path / site_type.name
        site_logos_path.mkdir(parents=True, exist_ok=True)

        logos[site_type.name][model_name] = sequence_logo(pwm, path)

    return logos


def sequence_logos_for_glycosylation_subtypes(subtypes=glycosylation_sub_types):
    logo_path = ANALYSES_OUTPUT_PATH / 'mimp' / 'logos'

    logo_path.mkdir(parents=True, exist_ok=True)
    path = logo_path / ('_'.join(subtypes) + '.svg')

    pwms = {}
    for model_name, pwm, site_type in iterate_mimp_models(subtypes, 'catch-all'):
        name = model_name.replace('all_enzymes_for_', '').replace('_', ' ')
        pwms[name] = pwm

    return sequence_logo(
        pwms, path, ncol=len(pwms), width=800, height=200,
        title='MIMP motifs for glycosylation sites', legend='right'
    )

