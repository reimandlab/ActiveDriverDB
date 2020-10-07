from xml.etree import ElementTree


def extract_drugs(path: str):
    root = ElementTree.iterparse(path, events=['start', 'end'])

    namespace = '{http://www.drugbank.ca}'
    drug = {}
    drugs = []
    parents = ['grandroot', 'root']


    def append_or_create(drug, key, value):
        if key not in drug:
            drug[key] = [value]
        else:
            drug[key].append(value)


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

            if tag == 'drug' and parent == 'drugbank':
                drug['type'] = elem.get('type')
                drug['created'] = elem.get('created')
                drug['updated'] = elem.get('updated')

            if grandparent == 'drugbank' and parent == 'drug':
                if tag == 'drugbank-id' and elem.get('primary', 'false') == 'true':
                    drug['id'] = elem.text
                if tag == 'name':
                    drug['name'] = elem.text

            if tag == 'group':
                append_or_create(drug, 'groups', elem.text)

            if tag == 'affected-organism':
            if grandparent == 'target':
                if parent == 'actions' and tag == 'action':
                    append_or_create(drug['targets'][-1], 'actions', elem.text)
                if parent == 'polypeptide' and tag == 'gene-name':
                    drug['targets'][-1]['gene_name'] = elem.text
                if parent == 'polypeptide' and tag == 'id':
                    drug['targets'][-1]['drugbank_target_id'] = elem.text

            if parent == 'target':
                if tag == 'organism':
                    drug['targets'][-1]['organism'] = elem.text
                if tag == 'polypeptide':
                    drug['targets'][-1]['protein_id'] = elem.get('id')
                    drug['targets'][-1]['protein_id_source'] = elem.get('source')
                if tag == 'name':
                    drug['targets'][-1]['target_name'] = elem.text

        if event == 'end':

            if parent == tag:
                parents.pop()
                parent = parents[-1]

            if tag == 'drug' and parent == 'drugbank':
                drugs.append(drug)
                drug = {}

        elem.clear()
    return drugs


def extract_targets(drugs):
    targets = []
    for drug in drugs:
        for target in drug.get('targets', []):
            targets.append(
                {
                    **target,
                    **{
                        'drug_' + key: value
                        for key, value in drug.items()
                    }
                }
            )
    return DataFrame(targets).drop(columns=['drug_targets'])


def extract_targets_for_addb():
    drugs = extract_drugs('full database.xml')
    targets = extract_targets(drugs)

    is_target_in_human = (targets.organism == 'Humans')
    is_target_protein_or_gene = (~targets.protein_id.isna() | ~targets.gene_name.isna())

    filtered_targets = targets[is_target_in_human & is_target_protein_or_gene].copy()
    filtered_targets['drug_groups'] = filtered_targets['drug_groups'].str.join(';')
    filtered_targets['actions'] = filtered_targets['actions'].str.join(';')
    assert set(filtered_targets['protein_id_source']) == {'Swiss-Prot', 'TrEMBL'}

    final_targets = filtered_targets[[
        'drug_id', 'drug_name', 'drug_type', 'drug_groups',
        'drug_created', 'drug_updated',
        'gene_name', 'protein_id',  'actions'
    ]]

    return final_targets.fillna('')
