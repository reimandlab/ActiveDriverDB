from database import bdb, bdb_refseq
from database import decode_csv
from database import get_or_create
from database import make_snv_key
from helpers.bioinf import decode_raw_mutation
from models import Mutation
from models import Protein


def get_genomic_muts(chrom, dna_pos, dna_ref, dna_alt):

    snv = make_snv_key(chrom, dna_pos, dna_ref, dna_alt)

    items = [
        decode_csv(item)
        for item in bdb[snv]
    ]

    # this could be speed up by: itemgetters, accumulative queries and so on
    for item in items:

        protein = Protein.query.get(item['protein_id'])
        item['protein'] = protein

        mutation, created = get_or_create(
            Mutation,
            protein=protein,
            protein_id=protein.id,
            position=item['pos'],
            alt=item['alt']
        )
        item['mutation'] = mutation
        item['type'] = 'genomic'
    return items


def iterate_affected_isoforms(gene_name, ref, pos, alt):
    """Returns all isoforms where specified mutation might happen.

    Explanation: shouldn't we look for refseq with gene name only?

    Well, we have to look for all isoforms of given gene which
    cover given mutation - so those with length Y: X <= Y, where
    X is the position (pos) of analysed mutation.

    There is on more constraint: some proteomic mutations cannot
    be caused by a single genomic mutations: F => S cannot be a
    result of a single SNV/SNP because neither UUU nor UUC could be
    changed to AGU or AGC in a single step.

    There are many such isoforms and simple lookup:
        gene_name => preferred_isoform, or
        gene_name => all_isoforms
    is not enough to satisfy all conditions.

    So what do we have here is (roughly) an equivalent to:

        from models import Gene

        # the function below should check if we don't have symbols
        # that are not representing any of known amino acids.

        is_mut_allowed(alt)

        # function above and below were not implemented but lets
        # assume that they throw a flow-changing exception

        can_be_result_of_single_snv(ref, alt)

        gene = Gene.query.filter_by(name=gene_name).one()
        return [
            isoform
            for isoform in gene.isoforms
            if (isoform.length >= pos and
                isoform.sequence[pos - 1] == ref)
        ]
    """
    hash_key = gene_name + ' ' + ref + str(pos) + alt
    refseqs = bdb_refseq[hash_key]

    return Protein.query.filter(Protein.refseq.in_(refseqs))


def get_protein_muts(gene_name, mut):
    """Retrieve corresponding mutations from all isoforms

    associated with given gene which are correct (i.e. they do not
    lie outside the range of a protein isoform and have the same
    reference residues). To speed up the lookup we use precomputed
    berkleydb hashmap.
    """
    ref, pos, alt = decode_raw_mutation(mut)

    items = []

    for isoform in iterate_affected_isoforms(gene_name, ref, pos, alt):

        mutation, created = get_or_create(
            Mutation,
            protein=isoform,
            position=pos,
            alt=alt
        )

        items.append(
            {
                'protein': isoform,
                'ref': ref,
                'alt': alt,
                'pos': pos,
                'mutation': mutation,
                'type': 'proteomic'
            }
        )
    return items


def represent_mutation(mutation, data_filter, representation_type=dict):

    affected_sites = mutation.get_affected_ptm_sites(data_filter)

    def repr_site(site):
        d = {
            'kinases': [
                kinase.to_json()
                for kinase in site.kinases
                ],
            'kinase_groups': [
                {'name': group.name}
                for group in site.kinase_groups
                ],
        }
        for k, v in site.to_json().items():
            d[k] = v
        return d

    return representation_type(
        (
            ('pos', mutation.position),
            ('alt', mutation.alt),
            ('ref', mutation.ref),
            ('cnt_ptm', len(affected_sites)),
            ('sites', [
                repr_site(site)
                for site in affected_sites
            ])
        )
    )


