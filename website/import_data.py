import csv
from collections import OrderedDict
from tqdm import tqdm
from database import db
from database import get_or_create
from helpers.parsers import parse_fasta_file
from helpers.parsers import parse_tsv_file
from helpers.parsers import parse_text_file
from helpers.parsers import count_lines
from models import Domain
from models import Gene
from models import InterproDomain
from models import Cancer
from models import Kinase
from models import KinaseGroup
from models import Protein
from models import Site
from models import BadWord
from models import GeneList
from models import CancerGeneListEntry
from import_mutations import load_mutations
from import_mutations import import_mappings
from flask import current_app


IMPORTERS = OrderedDict()


def importer(func):
    IMPORTERS[func.__name__] = func
    return func


def import_data(restrict_mutations_to):
    global genes
    genes, proteins = create_proteins_and_genes()
    load_sequences(proteins)
    select_preferred_isoforms(genes)
    load_disorder(proteins)
    load_domains(proteins)
    load_domains_hierarchy()
    load_domains_types()
    load_cancers()
    global kinase_protein_mappings
    kinase_protein_mappings = load_kinase_mapings()
    kinases, groups = load_sites(proteins)
    kinases, groups = load_kinase_classification(proteins, kinases, groups)
    load_pathways(genes)
    print('Adding kinases to the session...')
    db.session.add_all(kinases.values())
    print('Adding groups to the session...')
    db.session.add_all(groups.values())
    del kinases
    del groups
    remove_wrong_proteins(proteins)
    calculate_interactors(proteins)
    db.session.commit()
    with current_app.app_context():
        load_mutations(proteins, restrict_mutations_to)


@importer
def load_bad_words(filename='data/bad-words.txt'):

    list_of_profanities = []
    parse_text_file(
        filename,
        list_of_profanities.append,
        file_opener=lambda name: open(name, encoding='utf-8')
    )
    bad_words = [
        BadWord(word=word)
        for word in list_of_profanities
    ]
    return bad_words


@importer
def load_active_driver_gene_lists():
    tcga_gene_list = GeneList(name='TCGA')
    with open(
        'data/Supplementary_table_4__ActiveDriver_genes_p0.01.csv',
        newline=''
    ) as csv_file:
        count = count_lines(csv_file)
        csv_reader = csv.reader(csv_file)
        header = next(csv_reader)
        assert header == [
            "", "gene", "p", "fdr", "n_pSNVs", "cancer_type", "is_cancer_gene"
        ]
        list_entries = []
        for row in tqdm(csv_reader, total=count - 1):
            # select only records with 'PAN' in "cancer_type" column
            if row[5] != 'PAN':
                continue
            gene, created = get_or_create(Gene, name=row[1])
            entry = CancerGeneListEntry(
                gene=gene,
                p=float(row[2]),
                fdr=float(row[3]),
                is_cancer_gene=bool(row[-1])
            )
            list_entries.append(entry)
        tcga_gene_list.entries = list_entries
    return [tcga_gene_list]


def calculate_interactors(proteins):
    print('Precalculating interactors counts:')
    for protein in tqdm(proteins.values()):
        protein.interactors_count = protein._calc_interactors_count()


def load_pathways(genes):
    from models import Pathway
    new_genes = []

    def parser(data):
        nonlocal new_genes
        """Parse GTM file with pathhway descriptions.

        Args:
            data: a list of subsequent columns from a single line of GTM file

                For example::

                    ['CORUM:5419', 'HTR1A-GPR26 complex', 'GPR26', 'HTR1A']

        """
        gene_set_name = data[0]
        # Entry description can by empty
        entry_description = data[1].strip()

        entry_gene_names = [
            name.strip()
            for name in data[2:]
        ]

        pathway_genes = []

        for gene_name in entry_gene_names:
            if gene_name.lower() in genes:
                gene = genes[gene_name.lower()]
            else:
                gene = Gene(name=gene_name)
                genes[gene_name.lower()] = gene
                new_genes.append(gene)

            pathway_genes.append(gene)

        pathway = Pathway(
            description=entry_description,
            genes=pathway_genes
        )

        if gene_set_name.startswith('GO'):
            pathway.gene_ontology = int(gene_set_name[3:])
        elif gene_set_name.startswith('REAC'):
            pathway.reactome = int(gene_set_name[5:])
        else:
            print('Unknown gene set name: "%s"' % gene_set_name)

    filename = 'data/hsapiens.pathways.NAME.gmt'
    parse_tsv_file(filename, parser)

    db.session.add_all(new_genes)
    print(len(new_genes), 'new genes created')


def load_domains(proteins):

    print('Loading domains:')

    interpro_domains = dict()
    skipped = 0
    wrong_length = 0
    not_matching_chrom = []

    header = [
        'Ensembl Gene ID', 'Ensembl Transcript ID', 'Ensembl Protein ID',
        'Chromosome Name', 'Gene Start (bp)', 'Gene End (bp)',
        'RefSeq mRNA [e.g. NM_001195597]', 'Interpro ID',
        'Interpro Short Description', 'Interpro Description',
        'Interpro end', 'Interpro start'
    ]

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
                / max(len(domain), end - start)
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

    parse_tsv_file('data/biomart_protein_domains_20072016.txt', parser, header)

    print(
        'Domains loaded,', skipped, 'proteins skipped.',
        'Domains exceeding proteins length:', wrong_length,
        'Domains skipped due to not matching chromosomes:',
        len(not_matching_chrom)
    )


def load_domains_hierarchy():

    from re import compile

    print('Loading InterPro hierarchy:')

    expr = compile('^(?P<dashes>-*)(?P<interpro_id>\w*)::(?P<desc>.*?)::$')

    old_level = 0
    parent = None
    new_domains = []

    def parser(line):
        nonlocal parent, old_level, new_domains

        result = expr.match(line)

        dashes = result.group('dashes')
        interpro_id = result.group('interpro_id')
        description = result.group('desc')

        # at each level deeper two dashes are added, starting from 0
        level = len(dashes) / 2

        # look out for "jumps" - we do not expect those
        assert level - old_level <= 1 or level == 0

        if level == 0:
            parent = None

        domain, created = get_or_create(InterproDomain, accession=interpro_id)
        if created:
            domain.description = description
            new_domains.append(domain)

        if domain.description != description:
            print(
                'InteproDomain descriptions differs between database and',
                'hierarchy file: "{0}" vs "{1}" for: {2}'.format(
                    domain.description,
                    description,
                    interpro_id
                ))

        domain.level = level
        domain.parent = parent

        old_level = level
        parent = domain

    parse_text_file('data/ParentChildTreeFile.txt', parser)

    db.session.add_all(new_domains)
    print('Domains\' hierarchy built,', len(new_domains), 'new domains added.')


def load_domains_types():
    import xml.etree.ElementTree as ElementTree
    import gzip

    print('Loading extended InterPro annotations:')

    domains = {d.accession: d for d in InterproDomain.query.all()}

    with gzip.open('data/interpro.xml.gz') as interpro_file:
        tree = ElementTree.parse(interpro_file)

    entries = tree.getroot().findall('interpro')

    for entry in tqdm(entries):
        try:
            domain = domains[entry.get('id')]
        except KeyError:
            continue
        domain.type = entry.get('type')


def load_cancers():
    print('Loading cancer data:')

    def parser(line):
        code, name, color = line
        cancer, created = get_or_create(Cancer, name=name)
        if created:
            db.session.add(cancer)

        cancer.code = code

    parse_tsv_file('data/cancer_types.txt', parser)


def select_preferred_isoform(gene):
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
        return longest_isoforms[0]
    except IndexError:
        print('No isoform for:', gene)


def select_preferred_isoforms(genes):
    """Performs selection of preferred isoform,

    choosing the longest isoform which has the lowest refseq id
    """
    print('Choosing preferred isoforms:')

    for gene in tqdm(genes.values()):
        isoform = select_preferred_isoform(gene)
        if isoform:
            gene.preferred_isoform = isoform
        else:
            name = gene.name
            assert not gene.isoforms
            # remove(gene)
            print('Gene %s has no isoforms' % name)


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


def remove(object, soft=False):
    if soft:
        return db.session.expunge(object)
    else:
        return db.session.delete(object)


def remove_wrong_proteins(proteins, soft=True):
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

    with db.session.no_autoflush:
        removed = set()
        for protein in to_remove:
            removed.add(protein.refseq)

            gene = protein.gene
            gene.preferred_isoform = None

            remove(protein, soft)

            # remove object
            del proteins[protein.refseq]

    select_preferred_isoforms({
        gene.name.lower(): gene
        for gene in Gene.query.all()
    })

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
        if name.lower() not in genes:
            gene_data = {'name': name}
            gene_data['chrom'] = line[2][3:]    # remove chr prefix
            gene_data['strand'] = 1 if '+' else 0
            gene = Gene(**gene_data)
            genes[name.lower()] = gene
        else:
            gene = genes[name.lower()]

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


def get_preferred_gene_isoform(gene_name):
    if gene_name.lower() in genes:
        # if there is a gene, it has a preferred isoform
        return genes[gene_name.lower()].preferred_isoform


def load_kinase_mapings():
    """Read kinase -> protein name mappings into dict"""
    kinase_protein_map = {}

    def parser(line):
        kinase_name, protein_name = line
        kinase_protein_map[kinase_name] = protein_name

    parse_tsv_file('data/curated_kinase_IDs.txt', parser)

    return kinase_protein_map


def get_protein_by_kinase_name(name):
    """Return protein associated with given kinase name."""
    name = kinase_protein_mappings.get(name, name)
    return get_preferred_gene_isoform(name)


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
                    protein=get_protein_by_kinase_name(name)
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
