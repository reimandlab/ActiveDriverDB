from functools import lru_cache

from numpy import percentile
from sqlalchemy import func, distinct, case, literal_column

from database import db
from models import Mutation, Protein, Site


def variability_in_population(source, site_type=None, protein_subset=None, rare_threshold=0.5, only_primary=True):

    all_muts = func.count(distinct(Mutation.id)).label('muts_cnt')

    query = (
        db.session.query(
            func.count(distinct(case(
                [
                    (
                        source.maf_all <= rare_threshold / source.scale,
                        Mutation.id
                    )
                ],
                else_=literal_column('NULL')
            ))) * 100 / all_muts, all_muts
        ).select_from(source).join(Mutation).join(Protein)
    )

    if only_primary:
        query = query.filter(Protein.is_preferred_isoform)

    if site_type is None:
        query = query.filter(~Mutation.affected_sites.any())
    else:
        query = query.filter(Mutation.affected_sites.any(
            Site.type.contains(site_type)
        ))

    if protein_subset:
        query = query.filter(Protein.id.in_(protein_subset))

    return query


@lru_cache()
def proteins_variability(source, only_primary=True, site_type=None, without_sites=False):
    query = (
        db.session.query(
            Protein.id,
            func.sum(source.maf_all) / func.length(Protein.sequence)
        ).select_from(source).join(Mutation).join(Protein)
    )

    if only_primary:
        query = query.filter(Protein.is_preferred_isoform)

    if site_type is not None:
        assert not without_sites
        query = query.filter(Protein.sites.any(Site.type.contains(site_type)))

    if without_sites:
        query = query.filter(~Protein.sites.any())

    query = query.group_by(Protein.id)

    return query


def group_by_substitution_rates(source, only_primary=True, bins_count=100):
    # see http://journals.plos.org/plosgenetics/article?id=10.1371/journal.pgen.1004919#sec004:
    # "Global variation of PTM regions", though this operates only on mis-sense aminoacid substitutions
    # (non-sense and synonymous mutations are not considered)
    percentiles_per_bin = 100 / bins_count

    protein_rates = proteins_variability(source, only_primary).all()

    substitution_rates = [rate for protein, rate in protein_rates]

    bins = []

    previous_median = 0

    for i in range(1, bins_count + 1):
        bin_median = percentile(substitution_rates, i * percentiles_per_bin)

        bin_proteins = [
            protein
            for protein, rate in protein_rates
            if previous_median < rate <= bin_median
        ]
        bins.append(bin_proteins)

        previous_median = bin_median

    return bins

