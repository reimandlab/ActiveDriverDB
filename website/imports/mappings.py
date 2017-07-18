from collections import defaultdict
from database import make_snv_key
from database import encode_csv
from helpers.bioinf import decode_mutation
from helpers.bioinf import is_sequence_broken
from helpers.parsers import read_from_gz_files
from helpers.bioinf import get_human_chromosomes
from helpers.bioinf import determine_strand
from importlib import reload
from flask import current_app
import database
import gc


def import_mappings(
    proteins,
    mappings_dir='data/200616/all_variants/playground',
    mappings_file_pattern='annot_*.txt.gz'
):
    print('Importing mappings:')

    chromosomes = get_human_chromosomes()
    broken_seq = defaultdict(list)

    database.bdb.reset()
    database.bdb_refseq.reset()

    i = 0

    for line in read_from_gz_files(mappings_dir, mappings_file_pattern):
        chrom, pos, ref, alt, prot = line.rstrip().split('\t')

        assert chrom.startswith('chr')
        chrom = chrom[3:]

        assert chrom in chromosomes
        ref = ref.rstrip()

        snv = make_snv_key(chrom, pos, ref, alt)

        # new Coding Sequence Variants to be added to those already
        # mapped from given `snv` (Single Nucleotide Variation)
        new_variants = set()

        for dest in filter(bool, prot.split(',')):
            name, refseq, exon, cdna_mut, prot_mut = dest.split(':')
            assert refseq.startswith('NM_')
            # refseq = int(refseq[3:])
            # name and refseq are redundant with respect one to another

            assert exon.startswith('exon')
            exon = exon[4:]

            assert cdna_mut.startswith('c')
            cdna_ref, cdna_pos, cdna_alt = decode_mutation(cdna_mut)

            strand = determine_strand(ref, cdna_ref, alt, cdna_alt)

            assert prot_mut.startswith('p')
            # we can check here if a given reference nuc is consistent
            # with the reference amino acid. For example cytosine in
            # reference implies that there should't be a methionine,
            # glutamic acid, lysine nor arginine. The same applies to
            # alternative nuc/aa and their combinations (having
            # references (nuc, aa): (G, K) and alt nuc C defines that
            # the alt aa has to be Asparagine (N) - no other is valid).
            # Note: it could be used to compress the data in memory too
            aa_ref, aa_pos, aa_alt = decode_mutation(prot_mut)

            try:
                # try to get it from cache (`proteins` dictionary)
                protein = proteins[refseq]
            except KeyError:
                continue

            assert aa_pos == (int(cdna_pos) - 1) // 3 + 1

            broken_sequence_tuple = is_sequence_broken(protein, aa_pos, aa_ref, aa_alt)

            if broken_sequence_tuple:
                broken_seq[refseq].append(broken_sequence_tuple)
                continue

            is_ptm_related = protein.has_sites_in_range(aa_pos - 7, aa_pos + 7)

            # add new item, emulating set update
            item = encode_csv(
                strand,
                aa_ref,
                aa_alt,
                cdna_pos,
                exon,
                protein.id,
                is_ptm_related
            )

            new_variants.add(item)
            key = protein.gene.name + ' ' + aa_ref + str(aa_pos) + aa_alt
            database.bdb_refseq[key].update({refseq})

        database.bdb[snv].update(new_variants)

        i += 1
        if i % 200000 == 0:
            database.bdb.close()
            database.bdb_refseq.close()
            reload(database)
            database.bdb.open(current_app.config['BDB_DNA_TO_PROTEIN_PATH'])
            database.bdb_refseq.open(current_app.config['BDB_GENE_TO_ISOFORM_PATH'])
            gc.collect()

    return broken_seq
