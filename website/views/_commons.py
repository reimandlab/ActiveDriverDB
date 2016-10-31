from models import Protein
from models import Mutation
from database import bdb, bdb_refseq
from database import make_snv_key
from database import decode_csv
from database import get_or_create
from helpers.bioinf import decode_raw_mutation
from operator import attrgetter


def get_genomic_muts(chrom, dna_pos, dna_ref, dna_alt):
    snv = make_snv_key(chrom, dna_pos, dna_ref, dna_alt)

    items = [
        decode_csv(item)
        for item in bdb[snv]
    ]

    # this caould be speed up by: itemgetters, accumulative queries and so on

    for item in items:
        protein = Protein.query.get(
            item['protein_id']
        )
        item['protein'] = protein
        mutation, created = get_or_create(
            Mutation,
            protein_id=protein.id,
            position=item['pos'],
            alt=item['alt']
        )
        item['mutation'] = mutation
    return items


def get_affected_isoforms(gene_name, ref, pos, alt):
    """Returns all isoforms where specified mutation might happen.

    Explanation: shouldn't we look for refseq with gene name only?

    Well, we have to look for all isoforms of given gene which
    cover given mutation - so those with length Y: X <= Y, where
    X is the position (pos) of analysed mutation.

    There are many such isoforms and simple lookup:
        gene_name => preferred_isoform, or
        gene_name => all_isoforms
    is not enough to satisfy all conditions.

    So what do we have here is (rougly) an equivalent to:

        from models import Gene

        # the function below should check if we don't have symbols
        # that are not representing any of known amino acids.

        is_mut_allowed(alt)

        gene = Gene.query.filter_by(name=gene_name).one()
        return [
            isoform
            for isoform in gene.isoforms
            if (isoform.length >= pos and
                isoform.sequence[pos - 1] == ref)
        ]
    """
    hash_key = gene_name + ' ' + ref + str(pos) + alt

    return [
        Protein.query.filter_by(refseq=refseq).one()
        for refseq in bdb_refseq[hash_key]
    ]


def get_protein_muts(gene_name, mut):
    """Retrieve corresponding mutations from all isoforms

    associated with given gene which are correct (i.e. they do not
    lie outside the range of a protein isoform and have the same
    reference residues). To speed up the lookup we use precomputed
    berkleydb hashmap.
    """
    ref, pos, alt = decode_raw_mutation(mut)

    items = []

    for isoform in get_affected_isoforms(gene_name, ref, pos, alt):

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
                'mutation': mutation
            }
        )
    return items


def get_source_field(source):
    source_field_name = Mutation.source_fields[source]
    return source_field_name


def represent_mutations(mutations, filter_manager):

    source = filter_manager.get_value('Mutation.sources')
    source_field_name = get_source_field(source)

    get_source_data = attrgetter(source_field_name)
    get_mimp_data = attrgetter('meta_MIMP')

    response = []

    for mutation in mutations:

        field = get_source_data(mutation)
        mimp = get_mimp_data(mutation)

        metadata = {
            source: field.to_json(filter_manager.apply)
        }

        if mimp:
            metadata['MIMP'] = mimp.to_json()

        closest_sites = mutation.find_closest_sites()

        needle = {
            'pos': mutation.position,
            'value': field.get_value(filter_manager.apply),
            'category': mutation.impact_on_ptm,
            'alt': mutation.alt,
            'ref': mutation.ref,
            'meta': metadata,
            'sites': [
                site.to_json()
                for site in closest_sites
            ],
            'kinases': [
                kinase.to_json()
                for site in closest_sites
                for kinase in site.kinases
            ],
            'kinase_groups': [
                group.name
                for site in closest_sites
                for group in site.kinase_groups
            ],
            'cnt_ptm': mutation.cnt_ptm_affected,
            'summary': field.summary,
        }
        response.append(needle)

    return response
