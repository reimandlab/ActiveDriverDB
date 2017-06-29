import gzip
from collections import OrderedDict, defaultdict, namedtuple
from tqdm import tqdm
from database import db
from database import get_or_create
from helpers.parsers import parse_fasta_file
from helpers.parsers import parse_tsv_file
from helpers.parsers import parse_text_file
from models import Domain, UniprotEntry, MC3Mutation, InheritedMutation, Mutation
from models import Gene
from models import InterproDomain
from models import Cancer
from models import Kinase
from models import KinaseGroup
from models import Protein
from models import Site
from models import Pathway
from models import BadWord
from models import GeneList
from models import GeneListEntry
from helpers.commands import register_decorator
from operator import attrgetter


def get_proteins(cached_proteins={}, reload_cache=False):
    """Fetch all proteins from database as refseq => protein object mapping.

    By default proteins will be cached at first call and until cached_proteins
    is set explicitly to a (new, empty) dict() in subsequent calls, the
    cached results from the first time will be returned."""
    if reload_cache:
        cached_proteins.clear()
    if not cached_proteins:
        for protein in Protein.query:
            cached_proteins[protein.refseq] = protein
    return cached_proteins


IMPORTERS = OrderedDict()
importer = register_decorator(IMPORTERS)
# TODO: class with register? Should have fields as "parsed_count", "results"


def create_key_model_dict(model, key, lowercase=False):
    """Create 'entry.key: entry' dict mappings for all entries of given model."""
    key_getter = attrgetter(key)

    if lowercase:
        make_lowercase = str.lower

        def get_key(m):
            return make_lowercase(key_getter(m))
    else:
        get_key = key_getter

    return {
        get_key(m): m
        for m in model.query
    }


@importer
def proteins_and_genes(path='data/protein_data.tsv'):
    """Create proteins and genes based on data in a given file.

    If protein/gene already exists it will be skipped.

    Returns:
        list of created (new) proteins
    """
    # TODO where does the tsv file come from?
    print('Creating proteins and genes:')

    genes = create_key_model_dict(Gene, 'name', lowercase=True)
    known_proteins = get_proteins()

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
            gene_data = {
                'name': name,
                'chrom': line[2][3:],    # remove chr prefix
                'strand': 1 if '+' else 0
            }
            gene = Gene(**gene_data)
            genes[name.lower()] = gene
        else:
            gene = genes[name.lower()]

        # load protein
        refseq = line[1]

        # if protein is already in database no action is required
        if refseq in known_proteins:
            return

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

    parse_tsv_file(path, parser, header)

    cnt = sum(map(lambda g: len(g.isoforms) == 1, potentially_empty_genes))
    print('Duplicated that are only isoforms for gene:', cnt)
    print('Duplicated rows detected:', len(with_duplicates))
    return proteins.values()


@importer
def sequences(path='data/all_RefGene_proteins.fa'):
    proteins = get_proteins()

    print('Loading sequences:')

    overwritten = 0
    new_count = 0
    refseq = None

    def parser(line):
        nonlocal refseq, overwritten, new_count
        if line.startswith('>'):
            refseq = line[1:].rstrip()
            assert refseq in proteins
            if proteins[refseq].sequence:
                proteins[refseq].sequence = ''
                overwritten += 1
            else:
                new_count += 1
        else:
            proteins[refseq].sequence += line.rstrip()

    parse_fasta_file(path, parser)

    print('%s sequences overwritten' % overwritten)
    print('%s new sequences saved' % new_count)


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


@importer
def select_preferred_isoforms():
    """Perform selection of preferred isoform on all genes in database.

    As preferred isoform the longest isoform will be used. If two isoforms
    have the same length, the isoform with lower refseq identifier will be
    chosen. See implementation details in select_preferred_isoform()
    """
    print('Choosing preferred isoforms:')
    genes = Gene.query.all()

    for gene in tqdm(genes):
        isoform = select_preferred_isoform(gene)
        if isoform:
            gene.preferred_isoform = isoform
        else:
            name = gene.name
            assert not gene.isoforms
            # remove(gene)
            print('Gene %s has no isoforms' % name)


@importer
def disorder(path='data/all_RefGene_disorder.fa'):
    # library(seqinr)
    # load("all_RefGene_disorder.fa.rsav")
    # write.fasta(sequences=as.list(fa1_disorder), names=names(fa1_disorder),
    # file.out='all_RefGene_disorder.fa', as.string=T)
    print('Loading disorder data:')
    proteins = get_proteins()

    name = None

    def parser(line):
        nonlocal name
        if line.startswith('>'):
            name = line[1:].rstrip()
            assert name in proteins
        else:
            proteins[name].disorder_map += line.rstrip()

    parse_fasta_file(path, parser)

    for protein in proteins.values():
        assert len(protein.sequence) == protein.length


@importer
def domains(path='data/biomart_protein_domains_20072016.txt'):
    proteins = get_proteins()

    print('Loading domains:')

    interpro_domains = create_key_model_dict(InterproDomain, 'accession')
    new_domains = []

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
            # select similar domain occurrences with criteria being:
            domain for domain in protein.domains
            # - the same interpro id
            if domain.interpro == interpro and
            # - at least 75% of common coverage for shorter occurrence of domain
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

            domain = Domain(
                interpro=interpro,
                protein=protein,
                start=start,
                end=end
            )
            new_domains.append(domain)

    parse_tsv_file(path, parser, header)

    print(
        'Domains loaded,', skipped, 'proteins skipped.',
        'Domains exceeding proteins length:', wrong_length,
        'Domains skipped due to not matching chromosomes:',
        len(not_matching_chrom)
    )
    return new_domains


@importer
def domains_hierarchy(path='data/ParentChildTreeFile.txt'):
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
                'InterproDomain descriptions differs between database and',
                'hierarchy file: "{0}" vs "{1}" for: {2}'.format(
                    domain.description,
                    description,
                    interpro_id
                ))

        domain.level = level
        domain.parent = parent

        old_level = level
        parent = domain

    parse_text_file(path, parser)

    print('Domains\' hierarchy built,', len(new_domains), 'new domains added.')
    return new_domains


@importer
def domains_types(path='data/interpro.xml.gz'):
    import xml.etree.ElementTree as ElementTree
    import gzip

    print('Loading extended InterPro annotations:')

    domains = create_key_model_dict(InterproDomain, 'accession')

    with gzip.open(path) as interpro_file:
        tree = ElementTree.parse(interpro_file)

    entries = tree.getroot().findall('interpro')

    for entry in tqdm(entries):
        try:
            domain = domains[entry.get('id')]
        except KeyError:
            continue
        domain.type = entry.get('type')


@importer
def cancers(path='data/cancer_types.txt'):
    print('Loading cancer data:')

    cancers = []

    def parser(line):
        code, name, color = line
        cancer, created = get_or_create(Cancer, name=name)
        if created:
            cancers.append(cancer)

        cancer.code = code

    parse_tsv_file(path, parser)

    return cancers


def get_preferred_gene_isoform(gene_name):
    """Return a preferred isoform (protein) for a gene of given name.

    If there is a gene, it has a preferred isoform. Implemented as
    database query to avoid keeping all genes in memory - should be
    still feasible as there are not so many genes as proteins."""
    from sqlalchemy.orm.exc import NoResultFound

    # TODO consider same trick as for proteins: cache in mutable func arg

    try:
        gene = Gene.query.filter(Gene.name.ilike(gene_name)).one()
    except NoResultFound:
        return None
    return gene.preferred_isoform


@importer
def kinase_mappings(path='data/curated_kinase_IDs.txt'):
    """Create kinases from `kinase_name gene_name` mappings.

    For each kinase a `preferred isoforms` of given gene will be used.

    If given kinase already is in the database and has an isoform
    associated, the association will be superseded with the new one.

    Returns:
        list of created isoforms
    """
    known_kinases = create_key_model_dict(Kinase, 'name')

    new_kinases = []

    def parser(line):
        kinase_name, gene_name = line
        protein = get_preferred_gene_isoform(gene_name)

        if not protein:
            print(
                'No isoform for %s kinase mapped to %s gene!' %
                (kinase_name, gene_name)
            )
            return

        if kinase_name in known_kinases:
            kinase = known_kinases[kinase_name]
            if kinase.protein != protein:

                print(
                    'Overriding kinase-protein association for '
                    '%s kinase. Old isoform: %s; new isoform: %s.'
                    % (
                        kinase_name,
                        kinase.protein.refseq,
                        protein.refseq
                    )
                )
        else:
            new_kinases.append(
                Kinase(name=kinase_name, protein=protein)
            )

    parse_tsv_file(path, parser)

    return new_kinases


def get_or_create_kinases(chosen_kinases_names, known_kinases, known_kinase_groups):
    """Create a subset of known kinases and known kinase groups based on given
    list of kinases names ('chosen_kinases_names'). If no kinase or kinase group
    of given name is known, it will be created.

    Returns a tuple of sets:
        kinases, groups
    """
    kinases, groups = set(), set()

    for name in list(set(chosen_kinases_names)):

        # handle kinases group
        if name.endswith('_GROUP'):
            name = name[:-6]
            if name not in known_kinase_groups:
                known_kinase_groups[name] = KinaseGroup(name=name)
            groups.add(known_kinase_groups[name])
        # if it's not a group, it surely is a kinase:
        else:
            if name not in known_kinases:
                known_kinases[name] = Kinase(
                    name=name,
                    protein=get_preferred_gene_isoform(name)
                )
            kinases.add(known_kinases[name])

    return kinases, groups


@importer
def sites(path='data/site_table.tsv'):
    """Load sites from given file altogether with kinases which
    interact with these sites - kinases already in database will
    be reused, unknown kinases will be created

    Use following R code to reproduce `site_table.tsv` file:
    ```
        load('PTM_site_table.rsav')
        write.table(
            site_table, file='site_table.tsv',
            row.names=F, quote=F, sep='\t'
        )
    ```

    Args:
        path: to tab-separated-values file with sites to load

    Returns:
        list of created sites
    """
    proteins = get_proteins()

    print('Loading protein sites:')

    header = ['gene', 'position', 'residue', 'enzymes', 'pmid', 'type']

    sites = []

    known_kinases = create_key_model_dict(Kinase, 'name')
    known_groups = create_key_model_dict(KinaseGroup, 'name')

    def parser(line):

        refseq, position, residue, kinases_str, pmid, mod_type = line

        site_kinase_names = filter(bool, kinases_str.split(','))

        site_kinases, site_groups = get_or_create_kinases(
            site_kinase_names,
            known_kinases,
            known_groups
        )

        site = Site(
            position=int(position),
            residue=residue,
            pmid=pmid,
            protein=proteins[refseq],
            kinases=list(site_kinases),
            kinase_groups=list(site_groups),
            type=mod_type
        )

        sites.append(site)

    parse_tsv_file(path, parser, header)

    return sites


@importer
def kinase_classification(path='data/regphos_kinome_scraped_clean.txt'):

    known_kinases = create_key_model_dict(Kinase, 'name', True)
    known_groups = create_key_model_dict(KinaseGroup, 'name', True)

    new_groups = []

    print('Loading protein kinase groups:')

    header = [
        'No.', 'Kinase', 'Group', 'Family', 'Subfamily', 'Gene.Symbol',
        'gene.clean', 'Description', 'group.clean'
    ]

    def parser(line):

        # note that the subfamily is often absent
        group, family, subfamily = line[2:5]

        # the 'gene.clean' [6] fits better to the names
        # of kinases used in all other data files
        kinase_name = line[6]

        # 'group.clean' is not atomic and is redundant with respect to
        # family and subfamily. This check assures that in case of a change
        # the maintainer would be able to spot the inconsistency easily
        clean = family + '_' + subfamily if subfamily else family
        assert line[8] == clean

        if kinase_name.lower() not in known_kinases:
            kinase = Kinase(
                name=kinase_name,
                protein=get_preferred_gene_isoform(kinase_name)
            )
            known_kinases[kinase_name.lower()] = kinase

        # the 'family' corresponds to 'group' in the all other files
        if family.lower() not in known_groups:
            group = KinaseGroup(
                name=family
            )
            known_groups[family.lower()] = group
            new_groups.append(group)

        known_groups[family.lower()].kinases.append(known_kinases[kinase_name.lower()])

    parse_tsv_file(path, parser, header)

    return new_groups


@importer
def clean_from_wrong_proteins(soft=True):
    print('Removing proteins with misplaced stop codons:')
    from database import remove

    proteins = get_proteins()

    stop_inside = 0
    lack_of_stop = 0
    no_stop_at_the_end = 0

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

    select_preferred_isoforms()

    print('Removed proteins of sequences:')
    print('\twith stop codon inside (excluding the last pos.):', stop_inside)
    print('\twithout stop codon at the end:', no_stop_at_the_end)
    print('\twithout stop codon at all:', lack_of_stop)


@importer
def calculate_interactors():
    print('Precalculating interactors counts:')

    proteins = get_proteins()

    for protein in tqdm(proteins.values()):
        protein.interactors_count = protein._calc_interactors_count()


ListData = namedtuple('ListData', 'name path mutations_source')


@importer
def active_driver_gene_lists(
        lists=(
            ListData(
                name='Cancer (TCGA PanCancerAtlas)',
                path='data/mc3.v0.2.8.activedriver.txt',
                mutations_source=MC3Mutation
            ),
            ListData(
                name='Clinical (ClinVar)',
                path='data/ActiveDriver1_result_pvalue_less_0.01_InheritedMutation-2017-02-16.txt',
                mutations_source=InheritedMutation
            )
        ),
        fdr_cutoff=0.01
):
    current_gene_lists = [
        existing_list.name
        for existing_list in GeneList.query.all()
    ]
    gene_lists = []

    for list_data in lists:
        if list_data.name in current_gene_lists:
            print(
                'Skipping gene list %s: already present in database' %
                list_data.name
            )
            continue

        gene_list = GeneList(
            name=list_data.name,
            mutation_source_name=(
                list_data.mutations_source.name
                if list_data.mutations_source
                else None
            )
        )

        header = ['gene', 'p', 'fdr']

        to_high_fdr_count = 0
        list_entries = []

        def parser(line):
            gene_name, p_value, fdr = line
            p_value = float(p_value)
            fdr = float(fdr)

            nonlocal to_high_fdr_count

            if fdr >= fdr_cutoff:
                to_high_fdr_count += 1
                return

            gene, created = get_or_create(Gene, name=gene_name)

            entry = GeneListEntry(
                gene=gene,
                p=p_value,
                fdr=fdr
            )
            list_entries.append(entry)

            gene_list.entries = list_entries

        parse_tsv_file(list_data.path, parser, header)

        gene_lists.append(gene_list)

    return gene_lists


@importer
def external_references(path='data/HUMAN_9606_idmapping.dat.gz', refseq_path='data/LRG_RefSeqGene'):
    from models import Protein
    from models import ProteinReferences
    from models import EnsemblPeptide
    from sqlalchemy.orm.exc import NoResultFound

    references = defaultdict(list)

    def add_uniprot_accession(data):

        # full uniprot includes isoform (if relevant)
        full_uniprot, ref_type, value = data

        if ref_type == 'RefSeq_NT':
            # get protein
            refseq_nm = value.split('.')[0]

            if not refseq_nm or not refseq_nm.startswith('NM') or not full_uniprot:
                return

            try:
                protein = Protein.query.filter_by(refseq=refseq_nm).one()
            except NoResultFound:
                return

            try:
                uniprot, isoform = full_uniprot.split('-')
                isoform = int(isoform)
            except ValueError:
                # only one isoform ?
                # print('No isoform specified for', full_uniprot, refseq_nm)
                uniprot = full_uniprot
                isoform = 1

            reference, new = get_or_create(ProteinReferences, protein=protein)
            reference.uniprot_entries.append(UniprotEntry(accession=uniprot, isoform=isoform))
            references[uniprot].append(reference)

            if new:
                db.session.add(reference)

    ensembl_references_to_collect = {
        'Ensembl_PRO': 'peptide_id'
    }

    def add_references_by_uniprot(data):

        full_uniprot, ref_type, value = data

        if '-' in full_uniprot:
            uniprot, isoform = full_uniprot.split('-')
            uniprot_tied_references = references.get(uniprot, None)
            if not uniprot_tied_references:
                return

            relevant_references = []
            # select relevant references:
            for reference in uniprot_tied_references:
                if any(entry.isoform == int(isoform) for entry in reference.uniprot_entries):
                    relevant_references.append(reference)

        else:
            uniprot_tied_references = references.get(full_uniprot, None)
            if not uniprot_tied_references:
                return
            relevant_references = uniprot_tied_references

        if ref_type == 'UniProtKB-ID':
            # http://www.uniprot.org/help/entry_name
            # "Each >reviewed< entry is assigned a unique entry name upon integration into UniProtKB/Swiss-Prot"
            # Entry names comes in format: X_Y;
            # - for Swiss-Prot entry X is a mnemonic protein identification code (at most 5 characters)
            # - for TrEMBL entry X is the same as accession code (6 to 10 characters)
            x, y = value.split('_')

            if len(x) <= 5:
                for reference in relevant_references:
                    assert '-' not in full_uniprot
                    entry = UniprotEntry.query.filter_by(accession=full_uniprot, reference=reference).one()
                    entry.reviewed = True

            return

        if ref_type in ensembl_references_to_collect:

            attr = ensembl_references_to_collect[ref_type]

            for relevant_reference in relevant_references:
                attrs = {'reference': relevant_reference, attr: value}

                peptide, new = get_or_create(EnsemblPeptide, **attrs)

                if new:
                    db.session.add(peptide)

    def add_ncbi_mappings(data):
        '9606    3329    HSPD1   NG_008915.1     NM_199440.1     NP_955472.1     reference standard'
        taxonomy, entrez_id, gene_name, refseq_gene, lrg, refseq_nucleotide, t, refseq_peptide, p, category = data

        refseq_nm = refseq_nucleotide.split('.')[0]

        if not refseq_nm or not refseq_nm.startswith('NM'):
            return

        try:
            protein = Protein.query.filter_by(refseq=refseq_nm).one()
        except NoResultFound:
            return

        reference, new = get_or_create(ProteinReferences, protein=protein)

        reference.refseq_np = refseq_peptide.split('.')[0]
        reference.refseq_ng = refseq_gene.split('.')[0]
        reference.entrez_id = int(entrez_id)

        if new:
            db.session.add(reference)

        return

    parse_tsv_file(refseq_path, add_ncbi_mappings, file_header=[
        '#tax_id', 'GeneID', 'Symbol', 'RSG', 'LRG', 'RNA', 't', 'Protein', 'p', 'Category'
    ])

    parse_tsv_file(path, add_uniprot_accession, file_opener=gzip.open, mode='rt')
    parse_tsv_file(path, add_references_by_uniprot, file_opener=gzip.open, mode='rt')

    return [reference for reference_group in references.values() for reference in reference_group]


@importer
def pathways(path='data/hsapiens.pathways.NAME.gmt'):
    """Loads pathways from given '.gmt' file.

    New genes may be created and should automatically be added
    to the session with pathways as those have a relationship.
    """
    known_genes = create_key_model_dict(Gene, 'name', lowercase=True)

    pathways = []
    new_genes = []

    def parser(data):
        """Parse GTM file with pathway descriptions.

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
            name_lower = gene_name.lower()
            if name_lower in known_genes:
                gene = known_genes[name_lower]
            else:
                gene = Gene(name=gene_name)
                known_genes[name_lower] = gene
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
            raise Exception(
                'Unknown gene set name: "%s"' % gene_set_name
            )

    parse_tsv_file(path, parser)

    print(len(new_genes), 'new genes created')

    return pathways


@importer
def bad_words(path='data/bad-words.txt'):

    list_of_profanities = []
    parse_text_file(
        path,
        list_of_profanities.append,
        file_opener=lambda name: open(name, encoding='utf-8')
    )
    bad_words = [
        BadWord(word=word)
        for word in list_of_profanities
    ]
    return bad_words


@importer
def precompute_ptm_mutations():
    print('Counting mutations...')
    total = Mutation.query.filter_by(is_confirmed=True).count()
    mismatch = 0
    for mutation in tqdm(Mutation.query.filter_by(is_confirmed=True), total=total):
        pos = mutation.position
        is_ptm_related = mutation.protein.has_sites_in_range(pos - 7, pos + 7)
        if is_ptm_related != mutation.precomputed_is_ptm:
            mismatch += 1
            mutation.precomputed_is_ptm = is_ptm_related
    print('Precomputed values of ' + mismatch + ' mutations has been computed and updated')
    return []
