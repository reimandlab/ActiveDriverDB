#!/usr/bin/env python
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


tsv_references = get_references(
    # among available uniprot identifiers, the one from swissprot is the
    # most reliable, as it provides accession of manually reviewed entries
    # from curated database. Other options are: _sptrembl & _genname.
    'refseq_mrna',
    'uniprot_swissprot',
    'refseq_peptide',
)


references = {}


for row in tsv_references:
    data = row.split('\t')
    if data[0]:
        references[data[0]] = data[1:]


tsv_mrna_ensempl_peptide = get_references(
    'refseq_mrna',
    'ensembl_peptide_id'    # ensembl peptite id cannot be retrived together
    # with refseq_peptite as it results in incorrect mappings (one ensembl id
    # can point to multiple refseq_peptides and then biomart cannot tell
    # from which refseq_mrna those peptides comes)
)


for row in tsv_mrna_ensempl_peptide:
    data = row.split('\t')

    refseq_nm = data[0]

    if not refseq_nm:
        continue
    if refseq_nm not in references:
        # previous references were empty, let's say this directly
        references[refseq_nm] = ['', '']

    # has some ensembl peptide been already appended?
    if len(references[refseq_nm]) > 2:
        references[refseq_nm][2] += ' ' + data[1]
    else:
        references[refseq_nm].append(data[1])

with open('protein_external_references.tsv', 'w') as f:
    f.write('\n'.join(
        refseq + '\t' + '\t'.join(others)
        for refseq, others in references.items()
    ))
