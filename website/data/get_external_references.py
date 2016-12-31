#!/usr/bin/env python
from biomart import BiomartDataset


dataset = BiomartDataset(
    'http://www.ensembl.org/biomart',
    name='hsapiens_gene_ensembl'
)


response = dataset.search({
    'attributes': [
        # among available uniprot identifiers, the one from swissprot is the
        # most reliable, as it provides accession of manually reviewed entries
        # from curated database. Other options are: _sptrembl & _genname.
        'uniprot_swissprot',
        'refseq_mrna',
        'refseq_peptide',
        'ensembl_peptide_id'
    ]
})

with open('protein_external_references.tsv', 'w') as f:
    f.write(response.text)
