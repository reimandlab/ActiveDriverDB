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


def get_protein_muts(gene, mut):
    ref, pos, alt = decode_raw_mutation(mut)

    # get all refseq ids associated with given (pos, ref,
    # alt, gene) tuple by looking in berkleydb hashmap

    # why? we should look only for gene name!? TODO

    refseqs = bdb_refseq[gene + ' ' + ref + str(pos) + alt]

    items = []

    for refseq in refseqs:

        protein = Protein.query.filter_by(refseq=refseq).one()

        mutation, created = get_or_create(
            Mutation,
            protein_id=protein.id,
            position=pos,
            alt=alt
        )

        items.append(
            {
                'protein': protein,
                'ref': ref,
                'alt': alt,
                'pos': pos,
                'is_ptm': bool(mutation.is_ptm),
                'mutation': mutation,
                # TODO: make use of this:
                'is_correct': bool(pos > protein.length)
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
