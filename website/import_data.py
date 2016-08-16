import time
import psutil
from tqdm import tqdm
from app import app
from app import db
from collections import defaultdict
from database import get_or_create
from helpers.bioinf import decode_mutation
from helpers.bioinf import decode_raw_mutation
from website.models import Cancer
from website.models import CancerMutation
from website.models import Domain
from website.models import ExomeSequencingMutation
from website.models import Gene
from website.models import InterproDomain
from website.models import Kinase
from website.models import KinaseGroup
from website.models import MIMPMutation
from website.models import mutation_site_association
from website.models import Mutation
from website.models import Protein
from website.models import Site
from helpers.parsers import buffered_readlines
from helpers.parsers import parse_fasta_file
from helpers.parsers import parse_tsv_file
from helpers.parsers import chunked_list
from helpers.parsers import read_from_files


# remember to `set global max_allowed_packet=1073741824;` (it's max - 1GB)
# (otherwise MySQL server will be gone)
MEMORY_LIMIT = 2e9  # it can be greater than sql ma packet, since we will be
# counting a lot of overhead into the current memory usage. Adjust manually.

MEMORY_PERCENT_LIMIT = 80


def system_memory_percent():
    return psutil.virtual_memory().percent


def import_data():
    global genes
    genes, proteins = create_proteins_and_genes()
    load_sequences(proteins)
    select_preferred_isoforms(genes)
    load_disorder(proteins)
    load_domains(proteins)
    # cancers = load_cancers()
    kinases, groups = load_sites(proteins)
    kinases, groups = load_kinase_classification(proteins, kinases, groups)
    print('Adding kinases to the session...')
    db.session.add_all(kinases.values())
    print('Adding groups to the session...')
    db.session.add_all(groups.values())
    del kinases
    del groups
    removed = remove_wrong_proteins(proteins)
    print('Memory usage before first commit: ', memory_usage())
    calculate_interactors(proteins)
    db.session.commit()
    with app.app_context():
        mutations = load_mutations(proteins, removed)


def calculate_interactors(proteins):
    for protein in proteins.values():
        protein.interactors_count = protein._calc_interactors_count()


def get_proteins():
    return {protein.refseq: protein for protein in Protein.query.all()}


def load_domains(proteins):

    print('Loading domains:')

    interpro_domains = dict()
    skipped = 0
    wrong_length = 0
    not_matching_chrom = []

    def parser(line):

        nonlocal skipped, wrong_length, not_matching_chrom

        try:
            protein = proteins[line[6]]  # by refseq
        except KeyError:
            skipped += 1
            # commented out (too much to write to screen)
            """
            print(
                'Skipping domains for protein',
                line[6],
                '(no such a record in dataset)'
            )
            """
            return

        # If there is no data about the domains, skip this record
        if len(line) == 7:
            return

        try:
            assert len(line) == 12
        except AssertionError:
            print(line, len(line))

        # does start is lower than end?
        assert int(line[11]) < int(line[10])

        accession = line[7]

        # according to:
        # http://www.ncbi.nlm.nih.gov/pmc/articles/PMC29841/#__sec2title
        assert accession.startswith('IPR')

        start, end = int(line[11]), int(line[10])

        # TODO: the assertion fails for some domains: what to do?
        # assert end <= protein.length
        if end > protein.length:
            wrong_length += 1

        if line[3] != protein.gene.chrom:
            skipped += 1
            not_matching_chrom.append(line)
            return

        if accession not in interpro_domains:

            interpro = InterproDomain(
                accession=line[7],   # Interpro Accession
                short_description=line[8],   # Interpro Short Description
                description=line[9],   # Interpro Description
            )

            interpro_domains[accession] = interpro

        interpro = interpro_domains[accession]

        similar_domains = [
            # select similar domain occurances with criteria being:
            domain for domain in protein.domains
            # - the same interpro id
            if domain.interpro == interpro and
            # - at least 75% of common coverage for shorter occurance of domain
            (
                (min(domain.end, end) - max(domain.start, start))
                / min(len(domain), end - start)
                > 0.75
            )
        ]

        if similar_domains:
            try:
                assert len(similar_domains) == 1
            except AssertionError:
                print(similar_domains)
            domain = similar_domains[0]

            domain.start = min(domain.start, start)
            domain.end = max(domain.end, end)
        else:

            Domain(
                interpro=interpro,
                protein=protein,
                start=start,
                end=end
            )

    parse_tsv_file('data/biomart_protein_domains_20072016.txt', parser)

    print(
        'Domains loaded,', skipped, 'proteins skipped.',
        'Domains exceeding proteins length:', wrong_length,
        'Domains skipped due to not matching chromosomes:',
        len(not_matching_chrom)
    )


def select_preferred_isoforms(genes):
    """Performs selection of preferred isoform,

    choosing the longest isoform which has the lowest refseq id
    """
    print('Choosing preferred isoforms:')

    for gene in tqdm(genes.values()):
        max_length = 0
        longest_isoforms = []
        for isoform in gene.isoforms:
            length = isoform.length
            if length == max_length:
                longest_isoforms.append(isoform)
            elif length > max_length:
                longest_isoforms = [isoform]
                max_length = length

        # sort by refseq id (lower id will be earlier in the list)
        longest_isoforms.sort(key=lambda isoform: int(isoform.refseq[3:]))

        try:
            gene.preferred_isoform = longest_isoforms[0]
        except IndexError:
            print('No isoform for:', gene)


def load_sequences(proteins):

    print('Loading sequences:')

    refseq = None

    def parser(line):
        nonlocal refseq
        if line.startswith('>'):
            refseq = line[1:].rstrip()
            assert refseq in proteins
            assert proteins[refseq].sequence == ''
        else:
            proteins[refseq].sequence += line.rstrip()

    parse_fasta_file('data/all_RefGene_proteins.fa', parser)


def remove_wrong_proteins(proteins):
    stop_inside = 0
    lack_of_stop = 0
    no_stop_at_the_end = 0

    print('Removing proteins with misplaced stop codons:')

    to_remove = set()

    for protein in tqdm(proteins.values()):
        hit = False
        if '*' in protein.sequence[:-1]:
            stop_inside += 1
            hit = True
        if protein.sequence[-1] != '*':
            no_stop_at_the_end += 1
            hit = True
        if '*' not in protein.sequence:
            lack_of_stop += 1
            hit = True
        if hit:
            to_remove.add(protein)

    removed = set()
    for protein in to_remove:
        removed.add(protein.refseq)
        del proteins[protein.refseq]
        db.session.expunge(protein)

    print('Removed proteins of sequences:')
    print('\twith stop codon inside (excluding the last pos.):', stop_inside)
    print('\twithout stop codon at the end:', no_stop_at_the_end)
    print('\twithout stop codon at all:', lack_of_stop)

    return removed


def create_proteins_and_genes():

    print('Creating proteins and genes:')

    genes = {}
    proteins = {}

    coordinates_to_save = [
        ('txStart', 'tx_start'),
        ('txEnd', 'tx_end'),
        ('cdsStart', 'cds_start'),
        ('cdsEnd', 'cds_end')
    ]

    # a list storing refseq ids which occur at least twice in the file
    with_duplicates = []
    potentially_empty_genes = set()

    header = [
        'bin', 'name', 'chrom', 'strand', 'txStart', 'txEnd',
        'cdsStart', 'cdsEnd', 'exonCount', 'exonStarts', 'exonEnds',
        'score', 'name2', 'cdsStartStat', 'cdsEndStat', 'exonFrames'
    ]

    columns = tuple(header.index(x[0]) for x in coordinates_to_save)
    coordinates_names = [x[1] for x in coordinates_to_save]

    def parser(line):

        # load gene
        name = line[-4]
        if name not in genes:
            gene_data = {'name': name}
            gene_data['chrom'] = line[2][3:]    # remove chr prefix
            gene_data['strand'] = 1 if '+' else 0
            gene = Gene(**gene_data)
            genes[name] = gene
        else:
            gene = genes[name]

        # load protein
        refseq = line[1]

        # do not allow duplicates
        if refseq in proteins:

            with_duplicates.append(refseq)
            potentially_empty_genes.add(gene)

            """
            if gene.chrom in ('X', 'Y'):
                # close an eye for pseudoautosomal regions
                print(
                    'Skipping duplicated entry (probably belonging',
                    'to pseudoautosomal region) with refseq:', refseq
                )
            else:
                # warn about other duplicated records
                print(
                    'Skipping duplicated entry with refseq:', refseq
                )
            """
            return

        # from this line there is no processing of duplicates allowed
        assert refseq not in proteins

        protein_data = {'refseq': refseq, 'gene': gene}

        coordinates = zip(
            coordinates_names,
            [
                int(value)
                for i, value in enumerate(line)
                if i in columns
            ]
        )
        protein_data.update(coordinates)

        proteins[refseq] = Protein(**protein_data)

    parse_tsv_file('data/protein_data.tsv', parser, header)

    print('Adding proteins to the session...')
    db.session.add_all(proteins.values())

    cnt = sum(map(lambda g: len(g.isoforms) == 1, potentially_empty_genes))
    print('Duplicated that are only isoforms for gene:', cnt)
    print('Duplicated rows detected:', len(with_duplicates))
    return genes, proteins


def load_disorder(proteins):
    # library(seqinr)
    # load("all_RefGene_disorder.fa.rsav")
    # write.fasta(sequences=as.list(fa1_disorder), names=names(fa1_disorder),
    # file.out='all_RefGene_disorder.fa', as.string=T)
    print('Loading disorder data:')
    name = None

    def parser(line):
        nonlocal name
        if line.startswith('>'):
            name = line[1:].rstrip()
            assert name in proteins
        else:
            proteins[name].disorder_map += line.rstrip()

    parse_fasta_file('data/all_RefGene_disorder.fa', parser)

    for protein in proteins.values():
        assert len(protein.sequence) == protein.length


def load_cancers():
    cancers = {}
    with open('data/cancer_types.txt', 'r') as f:
        for line in f:
            line = line.rstrip()
            code, name, color = line.split('\t')
            assert code not in cancers
            cancers[code] = Cancer(code=code, name=name)
    print('Cancers loaded')
    return cancers


def load_mutations(proteins, removed):

    broken_seq = defaultdict(list)

    print('Loading mutations:')

    # a counter to give mutations.id as pk
    mutations_cnt = 1
    mutations = {}

    def flush_basic_mutations(mutations):
        for chunk in chunked_list(mutations.items()):
            db.session.bulk_insert_mappings(
                Mutation,
                [
                    {
                        'id': data[0],
                        'is_ptm': data[1],
                        'position': mutation[0],
                        'protein_id': mutation[1],
                        'alt': mutation[2]
                    }
                    for mutation, data in chunk
                ]
            )
            db.session.flush()

    def get_or_make_mutation(key, is_ptm):
        nonlocal mutations_cnt, mutations

        if key in mutations:
            mutation_id = mutations[key][0]
        else:
            try:
                mutation = Mutation.query.filter_by(
                    position=pos, protein_id=protein.id, alt=alt
                ).one()
                mutation_id = mutation.id
            except Exception:
                mutation_id = mutations_cnt
                mutations[key] = (mutations_cnt, is_ptm)
                mutations_cnt += 1
        return mutation_id

    db.session.commit()

    # MIMP MUTATIONS

    # load("all_mimp_annotations.rsav")
    # write.table(all_mimp_annotations, file="all_mimp_annotations.tsv",
    # row.names=F, quote=F, sep='\t')
    print('Loading MIMP mutations:')

    mimps = []
    sites = []

    header = [
        'gene', 'mut', 'psite_pos', 'mut_dist', 'wt', 'mt', 'score_wt',
        'score_mt', 'log_ratio', 'pwm', 'pwm_fam', 'nseqs', 'prob', 'effect'
    ]

    def parser(line):
        nonlocal mimps, mutations_cnt, sites

        refseq = line[0]
        mut = line[1]
        psite_pos = line[2]

        try:
            protein = proteins[refseq]
        except KeyError:
            return

        ref, pos, alt = decode_raw_mutation(mut)

        try:
            assert ref == protein.sequence[pos - 1]
        except (AssertionError, IndexError):
            broken_seq[refseq].append((protein.id, alt))
            return

        # TBD
        # print(line[9], line[10], protein.gene.name)

        assert line[13] in ('gain', 'loss')

        key = (pos, protein.id, alt)

        mutation_id = get_or_make_mutation(key, True)

        sites.extend([
            (site.id, mutation_id)
            for site in protein.sites
            if site.position == int(psite_pos)
        ])

        mimps.append(
            (
                mutation_id,
                int(line[3]),
                1 if line[13] == 'gain' else 0,
                line[9],
                line[10]
            )
        )

    parse_tsv_file('data/all_mimp_annotations.tsv', parser, header)

    flush_basic_mutations(mutations)

    for chunk in chunked_list(mimps):
        db.session.bulk_insert_mappings(
            MIMPMutation,
            [
                dict(
                    zip(
                        ('mutation_id', 'position_in_motif', 'effect',
                         'pwm', 'pwm_family'),
                        mutation_metadata
                    )
                )
                for mutation_metadata in chunk
            ]
        )
        db.session.flush()

    db.session.commit()

    for chunk in chunked_list(sites):
        db.engine.execute(
            mutation_site_association.insert(),
            [
                {
                    'site_id': s[0],
                    'mutation_id': s[1]
                }
                for s in chunk
            ]
        )
        db.session.flush()

    db.session.commit()

    del mimps
    del sites

    # CANCER MUTATIONS
    print('Loading cancer mutations:')

    from collections import Counter
    mutations_counter = Counter()

    mutations = {}

    def cancer_parser(line):

        nonlocal mutations_counter

        cancer_mutations = line[9].replace(';', ',').split(',')

        for mutation in cancer_mutations:
            mutation = mutation.split(':')

            refseq = mutation[1]
            mut = mutation[4]

            ref, pos, alt = decode_mutation(mut)

            try:
                protein = proteins[refseq]
            except KeyError:
                return

            try:
                assert ref == protein.sequence[pos - 1]
            except (AssertionError, IndexError):
                broken_seq[refseq].append((protein.id, alt))
                return

            sites = protein.get_sites_from_range(int(pos) - 7, int(pos) + 7)

            key = (pos, protein.id, alt)
            mutation_id = get_or_make_mutation(key, bool(sites))

            assert line[10].startswith('comments: ')

            cancer_name, sample, _ = line[10][10:].split(';')
            cancer, created = get_or_create(Cancer, name=cancer_name)
            if created:
                db.session.add(cancer)

            mutations_counter[
                (
                    mutation_id,
                    cancer.id,
                    sample
                )
            ] += 1

    parse_tsv_file('data/mutations/TCGA_muts_annotated.txt', cancer_parser)

    flush_basic_mutations(mutations)

    for chunk in chunked_list(mutations_counter.items()):
        db.session.bulk_insert_mappings(
            CancerMutation,
            [
                {
                    'mutation_id': mutation[0],
                    'cancer_id': mutation[1],
                    'sample_name': mutation[2],
                    'count': count
                }
                for mutation, count in chunk
            ]
        )
        db.session.flush()

    db.session.commit()

    del mutations_counter

    # ESP6500 MUTATIONS
    print('Loading ExomeSequencingProject 6500 mutations:')
    mutations = {}
    esp_mutations = []

    def esp_parser(line):

        line_mutations = line[9].replace(';', ',').split(',')

        for mutation in line_mutations:
            mutation = mutation.split(':')

            refseq = mutation[1]
            mut = mutation[4]

            ref, pos, alt = decode_mutation(mut)

            try:
                protein = proteins[refseq]
            except KeyError:
                return

            try:
                assert ref == protein.sequence[pos - 1]
            except (AssertionError, IndexError):
                broken_seq[refseq].append((protein.id, alt))
                return

            sites = protein.get_sites_from_range(pos - 7, pos + 7)

            key = (pos, protein.id, alt)
            mutation_id = get_or_make_mutation(key, bool(sites))

            metadata = line[20].split(';')

            # not flexible way to select MAF from metadata, but quite quick
            assert metadata[4].startswith('MAF=')

            maf_ea, maf_aa, maf_all = map(float, metadata[4][4:].split(','))

            esp_mutations.append(
                (
                    maf_ea,
                    maf_aa,
                    maf_all,
                    mutation_id
                )
            )

    parse_tsv_file('data/mutations/ESP6500_muts_annotated.txt', esp_parser)

    flush_basic_mutations(mutations)

    for chunk in chunked_list(esp_mutations):
        db.session.bulk_insert_mappings(
            ExomeSequencingMutation,
            [
                {
                    'maf_ea': mutation[0],
                    'maf_aa': mutation[1],
                    'maf_all': mutation[2],
                    'mutation_id': mutation[3]
                }
                for mutation in chunk
            ]
        )
        db.session.flush()

    db.session.commit()

    # 1000 GENOMES MUTATIONS (STUB)

    for line in read_from_files(
        'data/mutations/G1000',
        'G1000_chr*.txt.gz',
        skip_header=False
    ):
        data = line.rstrip().split('\t')
        line_mutations = data[9]
        metadata = data[20]
        # TODO
    print('Mutations loaded')


def get_preferred_gene_isoform(gene_name):
    if gene_name in genes:
        # if there is a gene, it has a preferred isoform
        return genes[gene_name].preferred_isoform


def make_site_kinases(proteins, kinases, kinase_groups, kinases_list):
    site_kinases, site_groups = [], []

    for name in kinases_list:

        if name.endswith('_GROUP'):
            name = name[:-6]
            if name not in kinase_groups:
                kinase_groups[name] = KinaseGroup(name=name)
            site_groups.append(kinase_groups[name])
        else:
            if name not in kinases:
                kinases[name] = Kinase(
                    name=name,
                    protein=get_preferred_gene_isoform(name)
                )
            site_kinases.append(kinases[name])

    return site_kinases, site_groups


def load_sites(proteins):
    # Use following R code to reproduce `site_table.tsv` file:
    # load("PTM_site_table.rsav")
    # write.table(site_table, file="site_table.tsv",
    #   row.names=F, quote=F, sep='\t')

    print('Loading protein sites:')

    header = ['gene', 'position', 'residue', 'enzymes', 'pmid', 'type']

    kinases = {}
    kinase_groups = {}

    def parser(line):

        refseq, position, residue, kinases_str, pmid, mod_type = line
        site_kinases, site_groups = make_site_kinases(
            proteins,
            kinases,
            kinase_groups,
            filter(bool, kinases_str.split(','))
        )
        Site(
            position=position,
            residue=residue,
            pmid=pmid,
            protein=proteins[refseq],
            kinases=site_kinases,
            kinase_groups=site_groups,
            type=mod_type
        )

    parse_tsv_file('data/site_table.tsv', parser, header)

    return kinases, kinase_groups


def load_kinase_classification(proteins, kinases, groups):

    print('Loading protein kinase groups:')

    header = [
        'No.', 'Kinase', 'Group', 'Family', 'Subfamily', 'Gene.Symbol',
        'gene.clean', 'Description', 'group.clean'
    ]

    def parser(line):

        # not that the subfamily is often abesnt
        group, family, subfamily = line[2:5]

        # the 'gene.clean' [6] fits better to the names
        # of kinases used in all other data files
        kinase_name = line[6]

        # 'group.clean' is not atomic and is redundant with respect to
        # family and subfamily. This check assures that in case of a change
        # the maintainer would be able to spot the inconsistency easily
        clean = family + '_' + subfamily if subfamily else family
        assert line[8] == clean

        if kinase_name not in kinases:
            kinases[kinase_name] = Kinase(
                name=kinase_name,
                protein=get_preferred_gene_isoform(kinase_name)
            )

        # the 'family' corresponds to 'group' in the all other files
        if family not in groups:
            groups[family] = KinaseGroup(
                name=kinase_name
            )

        groups[family].kinases.append(kinases[kinase_name])

    parse_tsv_file('data/regphos_kinome_scraped_clean.txt', parser, header)

    return kinases, groups


def memory_usage():
    import os
    import psutil
    process = psutil.Process(os.getpid())
    return process.memory_info().rss


def import_mappings(proteins):
    print('Importing mappings:')

    from helpers.bioinf import complement
    from helpers.bioinf import get_human_chromosomes
    from database import bdb
    from database import bdb_refseq
    from database import make_snv_key
    from database import encode_csv

    chromosomes = get_human_chromosomes()
    broken_seq = defaultdict(list)

    bdb.reset()
    bdb_refseq.reset()

    cnt_old_prots, cnt_new_prots = 0, 0

    for line in read_from_files(
        'data/200616/all_variants/playground',
        'annot_*.txt.gz'
    ):
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
            assert cdna_mut.startswith('c.')

            if (cdna_mut[2].lower() == ref and
                    cdna_mut[-1].lower() == alt):
                strand = '+'
            elif (complement(cdna_mut[2]).lower() == ref and
                    complement(cdna_mut[-1]).lower() == alt):
                strand = '-'
            else:
                raise Exception(line)

            cdna_pos = cdna_mut[3:-1]
            assert prot_mut.startswith('p.')
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

            try:
                assert aa_ref == protein.sequence[aa_pos - 1]
            except (AssertionError, IndexError):
                broken_seq[refseq].append((protein.id, aa_alt))
                continue

            sites = protein.get_sites_from_range(pos - 7, pos + 7)

            # add new item, emulating set update
            item = encode_csv(
                strand,
                aa_ref,
                aa_alt,
                cdna_pos,
                exon,
                protein.id,
                bool(sites)
            )

            new_variants.add(item)
            key = protein.gene.name + ' ' + aa_ref + str(aa_pos) + aa_alt
            bdb_refseq[key].update({refseq})

        bdb[snv].update(new_variants)

    return broken_seq
