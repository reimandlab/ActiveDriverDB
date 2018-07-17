from collections import defaultdict
from os.path import basename
from typing import Dict
import gzip

from genomic_mappings import make_snv_key, encode_csv
from helpers.bioinf import decode_mutation, DataInconsistencyError
from helpers.bioinf import is_sequence_broken
from helpers.parsers import read_from_gz_files
from helpers.bioinf import get_human_chromosomes
from helpers.bioinf import determine_strand
from flask import current_app
from database import bdb, bdb_refseq
from models import Protein


def import_genome_proteome_mappings(
    proteins: Dict[str, Protein],
    mappings_dir='data/200616/all_variants/playground',
    mappings_file_pattern='annot_*.txt.gz',
    bdb_dir=''
):
    print('Importing mappings:')

    chromosomes = get_human_chromosomes()
    broken_seq = defaultdict(list)

    bdb.reset()
    bdb.close()

    path = current_app.config['BDB_DNA_TO_PROTEIN_PATH']

    if bdb_dir:
        path = bdb_dir + '/' + basename(path)

    bdb.open(path, cache_size=20480 * 8 * 8 * 8 * 8)

    with bdb.cached_session(overwrite_db_values=True):
        for line in read_from_gz_files(mappings_dir, mappings_file_pattern, after_batch=bdb.flush_cache):
            try:
                chrom, pos, ref, alt, prot = line.rstrip().split('\t')
            except ValueError as e:
                print(e, line)
                continue

            assert chrom.startswith('chr')
            chrom = chrom[3:]

            assert chrom in chromosomes
            ref = ref.rstrip()

            # new Coding Sequence Variants to be added to those already
            # mapped from given `snv` (Single Nucleotide Variation)

            for dest in filter(bool, prot.split(',')):
                try:
                    name, refseq, exon, cdna_mut, prot_mut = dest.split(':')
                except ValueError as e:
                    print(e, line)
                    continue
                assert refseq.startswith('NM_')
                # refseq = int(refseq[3:])
                # name and refseq are redundant with respect one to another

                assert exon.startswith('exon')
                exon = exon[4:]

                assert cdna_mut.startswith('c')
                try:
                    cdna_ref, cdna_pos, cdna_alt = decode_mutation(cdna_mut)
                except ValueError as e:
                    print(e, line)
                    continue

                try:
                    strand = determine_strand(ref, cdna_ref, alt, cdna_alt)
                except DataInconsistencyError as e:
                    print(e, line)
                    continue

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

                is_ptm_related = protein.would_affect_any_sites(aa_pos)

                snv = make_snv_key(chrom, pos, cdna_ref, cdna_alt)

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

                bdb.cached_add(snv, item)

    return broken_seq


def export_all_potential_ptm_mutations(
    proteins: Dict[str, Protein],
    export_path='exported/all_potential_ptm_mutations.tsv.gz',
    mappings_dir='data/200616/all_variants/playground',
    mappings_file_pattern='annot_*.txt.gz',
    subset=None
):
    chromosomes = get_human_chromosomes()
    broken_seq = defaultdict(list)
    skipped_lines = 0
    all_lines = 0
    all_protein_mappings = 0
    skipped_mappings = 0
    ptm_related = 0

    with gzip.open(export_path, 'wt') as f:
        output = []

        def flush():
            nonlocal output
            for line in output:
                f.write(line)
            output = []

        for line in read_from_gz_files(mappings_dir, mappings_file_pattern, after_batch=lambda: flush()):
            all_lines += 1
            try:
                chrom, pos, ref, alt, prot = line.rstrip().split('\t')
            except ValueError as e:
                skipped_lines += 1
                print(e, line)
                continue

            assert chrom.startswith('chr')
            chrom = chrom[3:]

            assert chrom in chromosomes
            ref = ref.rstrip()

            # new Coding Sequence Variants to be added to those already
            # mapped from given `snv` (Single Nucleotide Variation)

            for dest in filter(bool, prot.split(',')):
                all_protein_mappings += 1
                try:
                    name, refseq, exon, cdna_mut, prot_mut = dest.split(':')
                except ValueError as e:
                    skipped_mappings += 1
                    print(e, line)
                    continue

                assert refseq.startswith('NM_')
                # name and refseq are redundant with respect one to another

                assert exon.startswith('exon')

                assert cdna_mut.startswith('c')
                try:
                    cdna_ref, cdna_pos, cdna_alt = decode_mutation(cdna_mut)
                except ValueError as e:
                    print(e, line)
                    skipped_mappings += 1
                    continue

                try:
                    strand = determine_strand(ref, cdna_ref, alt, cdna_alt)
                except DataInconsistencyError as e:
                    print(e, line)
                    skipped_mappings += 1
                    continue

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
                    skipped_mappings += 1
                    continue

                assert aa_pos == (int(cdna_pos) - 1) // 3 + 1

                broken_sequence_tuple = is_sequence_broken(protein, aa_pos, aa_ref, aa_alt)

                if broken_sequence_tuple:
                    broken_seq[refseq].append(broken_sequence_tuple)
                    skipped_mappings += 1
                    continue

                is_ptm_related = protein.would_affect_any_sites(aa_pos)

                if is_ptm_related:
                    ptm_types = protein.site_type_by_position[aa_pos]
                    if subset and not ptm_types.intersection(subset):
                        continue
                    ptm_related += 1
                    output.append('\t'.join(
                        [chrom, str(pos), strand, cdna_ref, str(cdna_pos), cdna_alt, refseq, aa_ref, str(aa_pos), aa_alt, ','.join(ptm_types)]
                    ) + '\n')

    print(ptm_related, skipped_mappings, skipped_lines, all_lines, all_protein_mappings)

    return broken_seq


def import_aminoacid_mutation_refseq_mappings(
    proteins: Dict[str, Protein],
    mappings_dir='data/200616/all_variants/playground',
    mappings_file_pattern='annot_*.txt.gz',
    bdb_dir=''
):
    print('Importing mappings:')

    chromosomes = get_human_chromosomes()

    bdb_refseq.reset()
    bdb_refseq.close()

    path = current_app.config['BDB_GENE_TO_ISOFORM_PATH']

    if bdb_dir:
        path = bdb_dir + '/' + basename(path)

    bdb_refseq.open(path, cache_size=20480 * 8 * 8 * 8 * 8)

    genes = {
        protein: protein.gene.name
        for protein in proteins.values()
    }

    with bdb_refseq.cached_session(overwrite_db_values=True):
        for line in read_from_gz_files(mappings_dir, mappings_file_pattern, after_batch=bdb_refseq.flush_cache):
            try:
                chrom, pos, ref, alt, prot = line.rstrip().split('\t')
            except ValueError:
                print('Import error: not enough values for "tab" split')
                print(line)
                continue

            assert chrom.startswith('chr')
            chrom = chrom[3:]

            assert chrom in chromosomes

            for dest in filter(bool, prot.split(',')):
                try:
                    name, refseq, exon, cdna_mut, prot_mut = dest.split(':')
                except ValueError:
                    print('Import error: not enough values for ":" split')
                    print(line)
                    print(dest)
                    continue

                try:
                    assert refseq.startswith('NM_')
                except AssertionError:
                    print(f'Import error: refseq does not start with NM_:')
                    print(line)
                    print(refseq)
                    continue

                try:
                    assert cdna_mut.startswith('c')
                    cdna_ref, cdna_pos, cdna_alt = decode_mutation(cdna_mut)

                    assert prot_mut.startswith('p')

                    aa_ref, aa_pos, aa_alt = decode_mutation(prot_mut)

                    try:
                        # try to get it from cache (`proteins` dictionary)
                        protein = proteins[refseq]
                    except KeyError:
                        continue

                    assert aa_pos == (int(cdna_pos) - 1) // 3 + 1

                    broken_sequence_tuple = is_sequence_broken(protein, aa_pos, aa_ref, aa_alt)

                    if broken_sequence_tuple:
                        continue

                    bdb_refseq.cached_add_integer(
                        genes[protein] + ' ' + aa_ref + str(aa_pos) + aa_alt,
                        protein.id
                    )
                except Exception as e:
                    print(f'Import error:')
                    print(e)
