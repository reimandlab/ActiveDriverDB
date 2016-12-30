#!/usr/bin/env python
from biomart import BiomartDataset


dataset = BiomartDataset(
    'http://www.ensembl.org/biomart',
    name='hsapiens_gene_ensembl'
)


response = dataset.search({
    'attributes': [
        'uniprot_genename',
        'refseq_mrna',
        'refseq_peptide',
        'ensembl_peptide_id'
    ]
})

with open('protein_mappings.tsv', 'w') as f:
    f.write(response.text)
