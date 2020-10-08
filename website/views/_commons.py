from collections import defaultdict

from models import Gene
from models.bio.drug import Drug, DrugTarget


def represent_mutation(mutation, data_filter, representation_type=dict):

    affected_sites = mutation.get_affected_ptm_sites(data_filter)

    return representation_type(
        (
            ('pos', mutation.position),
            ('alt', mutation.alt),
            ('ref', mutation.ref),
            ('cnt_ptm', len(affected_sites)),
            ('sites', [
                site.to_json(with_kinases=True)
                for site in affected_sites
            ])
        )
    )


def drugs_interacting_with_kinases(filter_manager, kinases):
    from sqlalchemy import and_

    kinase_gene_ids = [kinase.protein.gene_id for kinase in kinases if kinase.protein]
    drugs = filter_manager.query_all(
        Drug,
        lambda q: and_(
            q,
            Gene.id.in_(kinase_gene_ids)
        ),
        lambda query: query.join(DrugTarget)
    )
    drugs_by_kinase = defaultdict(set)
    for drug in drugs:
        for target_gene in drug.target_genes:
            drugs_by_kinase[target_gene].add(drug)
    return drugs_by_kinase
