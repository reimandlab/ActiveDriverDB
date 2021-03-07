from dataclasses import dataclass
from typing import List, Dict
from xml.etree import ElementTree

from pandas import DataFrame


def append_or_create(obj: dict, key: str, value):
    if key not in obj:
        obj[key] = [value]
    else:
        obj[key].append(value)


@dataclass
class State:
    ancestry: List[str]
    drugs: List[Dict]

    @property
    def drug(self) -> Dict:
        return self.drugs[-1]

    @property
    def target(self):
        return self.drug['targets'][-1]

    @property
    def parent(self):
        return self.ancestry[-1]

    @property
    def grandparent(self):
        return self.ancestry[-2]


def abort(message: str):
    raise ValueError(message)


def prefix_dot(actions):
    return {
        '.' + key: value
        for key, value in actions.items()
    }


def extract_drugs(path: str):
    root = ElementTree.iterparse(path, events=['start', 'end'])

    namespace = '{http://www.drugbank.ca}'
    state = State(
        ancestry=['grandroot', 'root'],
        drugs=[{}]
    )

    element: ElementTree.Element

    def finalise_drug():
        if not state.drug['name']:
            abort(f'No drug name for {state.drug}')
        else:
            state.drug.update(**{
                field: element.get(field)
                for field in ['type', 'created', 'updated']
            })
            state.drugs.append({})

    def set_drugbank_id():
        if element.get('primary', 'false') == 'true':
            state.drug.update(id=element.text)

    start_actions = prefix_dot({
        'target':
            lambda: append_or_create(state.drug, 'targets', {}),
        'target.polypeptide':
            lambda: append_or_create(state.target, 'polypeptides', {})
    })
    end_actions = prefix_dot({
        'drugbank.drug':
            finalise_drug,
        'drugbank.drug.drugbank-id':
            set_drugbank_id,
        'drugbank.drug.name':
            # note: ideally avoid ternary expressions in lambdas as eval order might be deceiving
            # but here we raise so it does not matter
            lambda: (
                state.drug.update(name=element.text)
                if element.text else
                abort(f'Name missing for {state.drug}; {element.keys()} {element.items()}')
            ),
        'group':
            lambda: append_or_create(state.drug, 'groups', element.text),
        'affected-organism':
            lambda: append_or_create(state.drug, 'affected_organisms', element.text),
        'target.actions.action':
            lambda: append_or_create(state.target, 'actions', element.text),
        'target.polypeptide.gene-name':
            lambda: state.target['polypeptides'][-1].update(gene_name=element.text),
        'target.organism':
            lambda: state.target.update(organism=element.text),
        'target.polypeptide':
            lambda: state.target['polypeptides'][-1].update(
                protein_id=element.get('id'),
                protein_id_source=element.get('source')
            ),
        'target.name':
            lambda: state.target.update(target_name=element.text)
    })

    for event, element in root:

        tag = element.tag
        if tag.startswith(namespace):
            tag = tag[len(namespace):]

        if event == 'start':
            state.ancestry.append(tag)

            current_path = '.'.join(state.ancestry)

            for action_path, action in start_actions.items():
                if current_path.endswith(action_path):
                    action()

        if event == 'end':

            current_path = '.'.join(state.ancestry)

            if state.parent == tag:
                state.ancestry.pop()

            for action_path, action in end_actions.items():
                if current_path.endswith(action_path):
                    action()

            element.clear()

    return state.drugs[:-1]


def extract_targets(drugs: List[Dict]) -> List[Dict]:
    targets = []
    for drug in drugs:
        for target in drug.get('targets', []):
            for polypeptide in target.get('polypeptides', []):
                targets.append(
                    {
                        **target,
                        **{
                            'drug_' + key: value
                            for key, value in drug.items()
                            if key != 'targets'
                        },
                        **polypeptide
                    }
                )
    return targets


def select_human_protein_or_gene_targets(targets: DataFrame):
    is_target_in_human = (targets.organism == 'Humans')
    is_target_protein_or_gene = (~targets.protein_id.isna() | ~targets.gene_name.isna())

    filtered_targets = targets[is_target_in_human & is_target_protein_or_gene].copy()
    return filtered_targets


def replace_missing(x, replacement_factory):
    return replacement_factory() if x != x else x


def prepare_targets(path: str) -> DataFrame:
    drugs = extract_drugs(path)
    targets = DataFrame(extract_targets(drugs))

    filtered_targets = select_human_protein_or_gene_targets(targets)

    assert set(filtered_targets['protein_id_source']) - {'Swiss-Prot', 'TrEMBL'} == set()

    for column in ['drug_groups', 'actions']:
        filtered_targets[column] = filtered_targets[column].apply(replace_missing, replacement_factory=list)

    final_targets = filtered_targets[[
        'drug_id', 'drug_name', 'drug_type', 'drug_groups',
        'drug_created', 'drug_updated',
        'gene_name', 'protein_id', 'actions'
    ]]

    return final_targets
