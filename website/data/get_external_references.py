#!/usr/bin/env python3
from collections import defaultdict
from biomart import BiomartDataset


dataset = BiomartDataset(
    'http://www.ensembl.org/biomart',
    name='hsapiens_gene_ensembl'
)


def get_references(*biomart_attr_names):
    response = dataset.search({
        'attributes': biomart_attr_names
    })
    return response.text.split('\n')


def add_references(references, primary_id, identifiers_list):

    for part_1 in range(0, len(identifiers_list), 2):
        group = [primary_id] + identifiers_list[part_1:part_1 + 2]
        tsv_references = get_references(*group)

        for row in tsv_references:
            data = row.split('\t')
            # data[0] points to primary id
            if data[0]:
                references[data[0]].update(zip(group[1:], data[1:]))


def save_references(references, identifiers_order, path='protein_external_references.tsv'):
    with open(path, 'w') as f:
        f.write('\n'.join(
            refseq + '\t' + '\t'.join(
                [others.get(key, '') for key in identifiers_order]
            )
            for refseq, others in references.items()
        ))


if __name__ == '__main__':
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
    all_references = defaultdict(dict)

    add_references(all_references, primary_id, non_ensembl_ids_to_fetch)
    add_references(all_references, primary_id, ensembl_ids_to_fetch)

    save_references(all_references, non_ensembl_ids_to_fetch + ensembl_ids_to_fetch)
