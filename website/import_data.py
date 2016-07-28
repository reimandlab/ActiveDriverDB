import time
import psutil
from tqdm import tqdm
from app import app
from app import db
from website.models import Protein
from website.models import Cancer
from website.models import Mutation
from website.models import Site
from website.models import Kinase
from website.models import KinaseGroup
# from website.models import CodingSequenceVariant
# from website.models import SingleNucleotideVariation
from website.models import Gene
from website.models import Domain
from website.models import InterproDomain


# remember to `set global max_allowed_packet=1073741824;` (it's max - 1GB)
# (otherwise MySQL server will be gone)
MEMORY_LIMIT = 2e9  # it can be greater than sql ma packet, since we will be
# counting a lot of overhead into the current memory usage. Adjust manually.

MEMORY_PERCENT_LIMIT = 80


def system_memory_percent():
    return psutil.virtual_memory().percent


def import_data():
    proteins = create_proteins_and_genes()
    load_sequences(proteins)
    select_preferred_isoforms()
    load_domains(proteins)
    load_disorder(proteins)
    # cancers = load_cancers()
    # load_mutations(proteins, cancers)
    #kinases, groups = load_sites(proteins)
    #kinases, groups = load_kinase_classification(proteins, kinases, groups)
    #db.session.add_all(kinases.values())
    #db.session.add_all(groups.values())
    print('Added kinases')
    print('Added proteins')
    #del kinases
    #del groups
    #del proteins
    # db.session.add_all(cancers.values())
    # print('Added cancers')
    print('Memory usage before commit: ', memory_usage())
    db.session.commit()
    print('Memory usage before cleaning: ', memory_usage())
    # del cancers
    print('Memory usage after cleaning: ', memory_usage())
    with app.app_context():
        load_mimp_mutations()   # this requires having sites already loaded
    start = time.clock()
    with app.app_context():
        proteins = {protein.refseq: protein for protein in Protein.query.all()}
        import_mappings(proteins)
    end = time.clock()
    print('Imported mappings in:', end - start)
    print('Memory usage after mappings: ', memory_usage())


def buffered_readlines(file_handle, line_count=5000):
    is_eof = False
    while not is_eof:
        buffer = []
        # read as much as line_count says
        for _ in range(line_count):
            line = file_handle.readline()

            # stop if needed
            if not line:
                is_eof = True
                break

            buffer.append(line)
        # release one row in a once from buffer
        for line in buffer:
            yield line


def count_lines(filename):
    with open(filename) as f:
        return sum(1 for line in f)


def parse_tsv_file(filename, parser, file_header=False):
    """Utility function wraping file parser

    It opens file, provides progress bar, and checks if the file header is the
    same as given (if provided). For each line parser will be called.
    """
    with open(filename) as f:
        if file_header:
            header = f.readline().rstrip().split('\t')
            assert header == file_header
        for line in tqdm(f, total=count_lines(filename)):
            line = line.rstrip().split('\t')
            parser(line)


def parse_fasta_file(filename, parser):
    with open(filename) as f:
        for line in tqdm(f, total=count_lines(filename)):
            parser(line)


def load_domains(proteins):

    print('Loading domains:')

    interpro_domains = dict()
    skipped = 0

    def parse(line):

        nonlocal skipped

        # Temporary? - if no data about the domains, skip it.
        if len(line) == 7:
            return

        try:
            assert len(line) == 12
        except AssertionError:
            print(line, len(line))
        # does start is lower than end?
        assert int(line[11]) < int(line[10])

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
        accession = line[7]

        # according to:
        # http://www.ncbi.nlm.nih.gov/pmc/articles/PMC29841/#__sec2title
        assert accession.startswith('IPR')

        if accession not in interpro_domains:

            assert int(line[10]) <= protein.length

            interpro = InterproDomain(
                accession=line[7],   # Interpro Accession
                short_description=line[8],   # Interpro Short Description
                description=line[9],   # Interpro Description
            )

            interpro_domains[accession] = interpro

        Domain(
            interpro=interpro_domains[accession],
            protein=protein,
            start=int(line[11]),
            end=int(line[10])
        )

    parse_tsv_file('data/biomart_protein_domains_20072016.txt', parse)

    print('Domains loaded,', skipped, 'proteins skipped')


def select_preferred_isoforms():
    """Performs selection of preferred isoform,

    choosing the longest isoform which has the lowest refseq id
    """
    print('Choosning preferred isoforms:')

    for gene in tqdm(Gene.query.all()):
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

    return proteins


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

    db.session.add_all(proteins.values())

    cnt = sum(map(lambda g: len(g.isoforms) == 1, potentially_empty_genes))
    print('Duplicated that are only isoforms for gene:', cnt)

    del genes

    print('Duplicated rows detected:', len(with_duplicates))
    return proteins


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
        assert len(protein.sequence) == len(protein.length)


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


def load_mutations(proteins, cancers):
    with open('data/ad_muts.tsv', 'r') as f:
        header = f.readline().rstrip().split('\t')
        assert header == ['gene', 'cancer_type', 'sample_id', 'position',
                          'wt_residue', 'mut_residue']
        for line in f:
            line = line.rstrip().split('\t')
            gene, _, sample_data, position, wt_residue, mut_residue = line
            _, _, cancer_code, sample_id, _, _ = sample_data.split(' ')

            Mutation(
                cancers[cancer_code],
                sample_id,
                position,
                wt_residue,
                mut_residue,
                proteins[gene]
            )
    print('Mutations loaded')


def load_mimp_mutations():
    from os.path import commonprefix

    # load("all_mimp_annotations.rsav")
    # write.table(all_mimp_annotations, file="all_mimp_annotations.tsv",
    # row.names=F, quote=F, sep='\t')

    print('Loading mimp mutations:')

    header = [
        'gene', 'mut', 'psite_pos', 'mut_dist', 'wt', 'mt', 'score_wt',
        'score_mt', 'log_ratio', 'pwm', 'pwm_fam', 'nseqs', 'prob', 'effect'
    ]

    def parser(line):
        refseq = line[0]
        mut = line[1]
        psite_pos = line[2]

        protein = Protein.query.filter_by(refseq=refseq).first()
        pos = int(mut[1:-1])
        assert protein.sequence[pos] == mut[0]

        # TBD
        # print(line[9], line[10], protein.gene.name)

        Mutation(
            position=pos,
            mut_residue=mut[-1],
            protein=protein,
            sites=[
                site
                for site in protein.sites
                if site.position == psite_pos
            ],
            position_in_motif=len(commonprefix((line[4], line[5])))
        )

    parse_tsv_file('data/all_mimp_annotations.tsv', parser, header)

    print('Mutations loaded')


def get_preferred_gene_isoform(gene_name):
    gene = Gene.query.filter_by(name=gene_name).one_or_none()
    if gene:
        # if there is a gene, it has a preferred isoform
        return gene.preferred_isoform


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

    load_tsv_file('data/site_table.tsv', parser, header)

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


def get_files(path, pattern):
    import glob
    return glob.glob(path + '/' + pattern)


def memory_usage():
    import os
    import psutil
    process = psutil.Process(os.getpid())
    return process.memory_info().rss


def get_or_create(model, **kwargs):
    from sqlalchemy.orm.exc import NoResultFound
    try:
        return model.query.filter_by(**kwargs).one(), False
    except NoResultFound:
        return model(**kwargs), True


def import_mappings(proteins):
    print('Importing mappings:')

    files = get_files('data/200616/all_variants/playground', 'annot_*.txt.gz')

    import gzip

    from helpers.bioinf import complement
    from helpers.bioinf import get_human_chromosomes
    from database import bdb
    from database import bdb_refseq
    from database import make_snv_key

    chromosomes = get_human_chromosomes()

    bdb.reset()
    bdb_refseq.reset()

    cnt_old_prots, cnt_new_prots = 0, 0

    for filename in tqdm(files):

        with gzip.open(filename, 'rb') as f:
            next(f)  # skip the header
            for line in buffered_readlines(f, 10000):

                line = line.decode("latin1")
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
                    aa_ref = prot_mut[2]
                    aa_pos = prot_mut[3:-1]
                    aa_alt = prot_mut[-1]

                    try:
                        # try to get it from cache (`proteins` dictionary)
                        protein = proteins[refseq]
                        cnt_old_prots += 1
                        # if cache has been flushed, retrive from database
                        if not protein:
                            protein = Protein.query.filter_by(refseq=refseq).\
                                first()
                            proteins[refseq] = protein
                    except KeyError:
                        # if the protein was not in the cache,
                        # create it and add to the cache
                        print(
                            'Create protein from mappings:', refseq,
                            'it will not have any other data!'
                        )
                        gene, _ = get_or_create(Gene, name=name)
                        protein = Protein(refseq=refseq, gene=gene)
                        proteins[refseq] = protein
                        cnt_new_prots += 1
                        db.session.add(protein)
                        db.session.flush()
                        db.session.refresh(protein)

                    assert int(aa_pos) == (int(cdna_pos) - 1) // 3 + 1

                    # add new item, emulating set update
                    item = strand + aa_ref + aa_alt + ':'.join((
                        '%x' % int(cdna_pos), exon, '%x' % protein.id))
                    new_variants.add(item)
                    key = protein.gene.name + ' ' + aa_ref + aa_pos + aa_alt
                    bdb_refseq[key].update({refseq})

                bdb[snv].update(new_variants)

        print(filename, 'loaded succesfully')
        break   # TODO: remove this temporary constraint

    print('Read', len(files), 'files with genome -> protein mappings, ')
    print(cnt_new_prots, 'new proteins created & ', cnt_old_prots, 'used')
