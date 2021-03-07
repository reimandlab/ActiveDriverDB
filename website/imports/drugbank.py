from typing import List, Dict
from xml.etree import ElementTree

from pandas import DataFrame


def extract_drugs(path: str):
    root = ElementTree.iterparse(path, events=['start', 'end'])

    namespace = '{http://www.drugbank.ca}'
    drug: dict = {}
    drugs = []
    parents = ['grandroot', 'root']

    def append_or_create(obj: dict, key: str, value):
        if key not in obj:
            obj[key] = [value]
        else:
            obj[key].append(value)

    for event, elem in root:

        tag = elem.tag
        if tag.startswith(namespace):
            tag = tag[len(namespace):]

        parent = parents[-1]
        grandparent = parents[-2]

        if event == 'start':
            parents.append(tag)

            if tag == 'target':
                append_or_create(drug, 'targets', {})

            if parent == 'target':
                if tag == 'polypeptide':
                    target = drug['targets'][-1]
                    append_or_create(target, 'polypeptides', {})

        if event == 'end':

            if parent == tag:
                parents.pop()
                parent = parents[-1]
                grandparent = parents[-2]

            if tag == 'drug' and parent == 'drugbank':
                drug['type'] = elem.get('type')
                drug['created'] = elem.get('created')
                drug['updated'] = elem.get('updated')

            if tag == 'group':
                append_or_create(drug, 'groups', elem.text)

            if tag == 'affected-organism':
                append_or_create(drug, 'affected_organisms', elem.text)

            if grandparent == 'target':
                target = drug['targets'][-1]
                if parent == 'actions' and tag == 'action':
                    append_or_create(target, 'actions', elem.text)
                if parent == 'polypeptide' and tag == 'gene-name':
                    target['polypeptides'][-1]['gene_name'] = elem.text
                if parent == 'polypeptide' and tag == 'id':
                    target['drugbank_target_id'] = elem.text

            if parent == 'target':
                target = drug['targets'][-1]
                if tag == 'organism':
                    target['organism'] = elem.text
                if tag == 'polypeptide':
                    target['polypeptides'][-1]['protein_id'] = elem.get('id')
                    target['polypeptides'][-1]['protein_id_source'] = elem.get('source')
                if tag == 'name':
                    target['target_name'] = elem.text

            if grandparent == 'drugbank' and parent == 'drug':
                if tag == 'drugbank-id' and elem.get('primary', 'false') == 'true':
                    drug['id'] = elem.text
                if tag == 'name':
                    if not elem.text:
                        raise ValueError(f'Name missing for {drug}; {elem.keys()} {elem.items()}')
                    drug['name'] = elem.text

            if tag == 'drug' and parent == 'drugbank':
                if not drug['name']:
                    raise ValueError(f'No drug name for {drug}')
                drugs.append(drug)
                drug = {}

            elem.clear()
    return drugs


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
