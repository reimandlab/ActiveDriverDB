#!/usr/bin/env python3
from collections import defaultdict
from biomart import BiomartDataset
from tqdm import tqdm

dataset = BiomartDataset(
    'http://www.ensembl.org/biomart',
    name='hsapiens_gene_ensembl'
)


def get_references(*biomart_attr_names):
    response = dataset.search({
        'attributes': biomart_attr_names
    })
    return response.text.split('\n')


def add_references(references, primary_id_name, identifiers_list, primary_id_prefix='NM_', allow_dups=False):

    skipped = 0

    for identifier in identifiers_list:
        group = [primary_id_name, identifier]
        tsv_references = get_references(*group)

        for row in tqdm(tsv_references):
            data = row.split('\t')

            primary_id = data[0]

            if not primary_id or len(data) == 1:
                continue

            if not primary_id.startswith(primary_id_prefix):
                skipped += 1
                continue

            refs = references[data[0]]
            value = data[1]

            if not value:
                continue

            if identifier in refs and refs[identifier]:
                if allow_dups:
                    refs[identifier] += ' ' + value
                else:
                    print('Duplicated value for', identifier, primary_id, refs[identifier], value)
            else:
                refs[identifier] = value

    print(
        'Skipped', skipped, 'results where primary id do not match:',
        primary_id_prefix
    )


def save_references(references, identifiers_order, path='protein_external_references.tsv'):
    with open(path, 'w') as f:
        f.write('\n'.join(
            refseq + '\t' + '\t'.join(
                [others.get(key, '') for key in identifiers_order]
            )
            for refseq, others in references.items()
        ))


primary_id = 'refseq_mrna'

non_ensembl_ids_to_fetch = [
    # among available uniprot identifiers, the one from swissprot is the
    # most reliable, as it provides accession of manually reviewed entries
    # from curated database. Other options are: _sptrembl & _genname.
    'uniprotswissprot',
    'refseq_peptide',
    'entrezgene'
]

ensembl_ids_to_fetch = [
    'ensembl_peptide_id'    # ensembl peptite id cannot be retrieved together
    # with refseq_peptite as it results in incorrect mappings (one ensembl id
    # can point to multiple refseq_peptides and then biomart cannot tell
    # from which refseq_mrna those peptides comes)
]

identifiers_order = non_ensembl_ids_to_fetch + ensembl_ids_to_fetch

if __name__ == '__main__':
    all_references = defaultdict(dict)

    add_references(all_references, primary_id, non_ensembl_ids_to_fetch)
    add_references(all_references, primary_id, ensembl_ids_to_fetch, allow_dups=True)

    save_references(all_references, identifiers_order)
