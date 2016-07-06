from app import db, app
from website.models import Protein
from website.models import Cancer
from website.models import Mutation
from website.models import Site
from website.models import Kinase
from website.models import KinaseGroup
from website.models import CodingSequenceVariant
from website.models import SingleNucleotideVariation
from website.models import Gene


def import_data():
    # proteins = create_proteins_with_seq_old()
    # load_protein_refseq_old(proteins)
    proteins = create_proteins_and_genes()
    load_sequences(proteins)
    # load_disorder(proteins)
    # cancers = load_cancers()
    # load_mutations(proteins, cancers)
    # kinases, groups = load_sites(proteins)
    # kinases, groups = load_kinase_classification(proteins, kinases, groups)
    # db.session.add_all(kinases.values())
    # db.session.add_all(groups.values())
    # print('Added kinases')
    # db.session.add_all(cancers.values())
    # print('Added cancers')
    db.session.add_all(proteins.values())
    print('Added proteins')
    print('Memory usage before commit: ', memory_usage())
    db.session.commit()
    print('Memory usage before cleaning: ', memory_usage())
    # del cancers
    # del kinases
    # del groups
    print('Memory usage after cleaning: ', memory_usage())
    with app.app_context():
        # proteins = Protein.query.all()
        import_mappings(proteins)
    print('Memory usage after mappings: ', memory_usage())


def load_sequences(proteins):
    with open('data/all_RefGene_proteins.fa', 'r') as f:
        refseq = None
        for line in f:
            if line.startswith('>'):
                refseq = line[1:].rstrip()
                assert refseq in proteins
                assert proteins[refseq].sequence == ''
            else:
                proteins[refseq].sequence += line.rstrip()
    print('Sequences loaded')
    return proteins


def create_proteins_and_genes():

    proteins = {}
    genes = {}

    coordinates_to_save = {
        'txStart': 'tx_start',
        'txEnd': 'tx_end',
        'cdsStart': 'cds_start',
        'cdsEnd': 'cds_end'
    }

    # a list storing refseq ids which occur at least twice in the file
    with_duplicates = []

    with open('data/protein_data.tsv') as f:
        header = f.readline().rstrip().split('\t')

        assert header == ['bin', 'name', 'chrom', 'strand', 'txStart', 'txEnd',
                'cdsStart', 'cdsEnd', 'exonCount', 'exonStarts', 'exonEnds',
                'score', 'name2', 'cdsStartStat', 'cdsEndStat', 'exonFrames']

        columns = (header.index(key) for key in coordinates_to_save)

        for line in f:
            line = line.rstrip().split('\t')

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
                continue

            # from this line there is no processing of duplicates allowed
            assert refseq not in proteins

            protein_data = {'refseq': refseq, 'gene': gene}

            coordinates = zip(
                coordinates_to_save.values(),
                [
                    int(value)
                    for i, value in enumerate(line)
                    if i in columns
                ]
            )
            protein_data.update(coordinates)

            protein = Protein(**protein_data)
            proteins[refseq] = protein

    print('Duplicated rows detected:', len(with_duplicates))
    print('Proteins and genes created')
    return proteins


def load_disorder(proteins):
    with open('data/longest_isoform_proteins_disorder.fa', 'r') as f:
        name = None
        for line in f:
            if line.startswith('>'):
                name = line[1:].rstrip()
                assert name in proteins
            else:
                proteins[name].disorder_map += line.rstrip()
    print('Disorder data loaded')


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
                    protein=proteins.get(name, None)
                )
            site_kinases.append(kinases[name])

    return site_kinases, site_groups


def load_sites(proteins):
    with open('data/psite_table.tsv', 'r') as f:
        header = f.readline().rstrip().split('\t')
        assert header == ['gene', 'position', 'residue', 'kinase', 'pmid']
        kinases = {}
        kinase_groups = {}
        for line in f:
            line = line.rstrip()
            gene, position, residue, kinases_str, pmid = line.split('\t')
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
                protein=proteins[gene],
                kinases=site_kinases,
                kinase_groups=site_groups
            )
    print('Protein sites loaded')
    return kinases, kinase_groups


def load_kinase_classification(proteins, kinases, groups):

    with open('data/regphos_kinome_scraped_clean.txt', 'r') as f:
        header = f.readline().rstrip().split('\t')

        assert header == [
            'No.', 'Kinase', 'Group', 'Family', 'Subfamily', 'Gene.Symbol',
            'gene.clean', 'Description', 'group.clean']

        for line in f:
            line = line.rstrip().split('\t')

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
                    protein=proteins.get(kinase_name, None),
                )

            # the 'family' corresponds to 'group' in the all other files
            if family not in groups:
                groups[family] = KinaseGroup(
                    name=kinase_name
                )

            groups[family].kinases.append(kinases[kinase_name])

    return kinases, groups


def get_files(path, pattern):
    import glob
    return glob.glob(path + '/' + pattern)


def memory_usage():
    import os
    import psutil
    process = psutil.Process(os.getpid())
    return process.memory_info().rss


MEMORY_LIMIT = 2e9


def get_or_create(model, **kwargs):
    from sqlalchemy.orm.exc import NoResultFound
    try:
        return model.query.filter_by(**kwargs).one(), False
    except NoResultFound:
        return model(**kwargs), True


def import_mappings(proteins):

    files = get_files('data/200616/all_variants/playground', 'annot_*.txt.gz')

    genomic_muts = {}
    protein_muts = []

    import gzip

    from helpers.bioinf import complement
    from helpers.bioinf import get_human_chromosomes
    from operator import itemgetter

    chromosomes = get_human_chromosomes()

    cnt_old_prots, cnt_new_prots = 0, 0
    a = 1

    for filename in files:
        if a > 2:
            break
        a += 1

        with gzip.open(filename, 'rb') as f:
            next(f)  # skip the header
            for i, line in enumerate(f):

                # flush after reaching memory limit but check
                # memory usage only once per 25 analysed rows
                if i % 25 == 0:
                    usage = memory_usage()
                    if usage > MEMORY_LIMIT:
                        print(
                            'Memory usage (', usage, ') greater than limit (',
                            MEMORY_LIMIT, '), flushing cache to the database'
                        )
                        # new proteins will be flushed along with SNVs and CSVs
                        # clear proteins cache (note: by looping, not by
                        # dict.fromkeys - so we do not create a copy of keys)
                        for key in proteins:
                            proteins[key] = None
                        # flush SNVs and CSVs:
                        db.session.add_all(protein_muts)
                        db.session.commit()
                        genomic_muts = {}
                        protein_muts = []

                line = line.decode("latin1")
                chrom, pos, ref, alt, prot = line.rstrip().split('\t')
                assert chrom.startswith('chr')
                chrom = chrom[3:]
                assert chrom in chromosomes

                snv_data = {
                    'chrom': chrom,
                    'pos': int(pos),
                    'ref': ref,
                    'alt': alt
                }

                try:
                    # get snv from cache
                    snv, is_new = genomic_muts[tuple(snv_data.values())]
                except KeyError:
                    # get from database or create new
                    snv, is_new = get_or_create(
                        SingleNucleotideVariation,
                        **snv_data
                    )
                    # add to cache
                    genomic_muts[tuple(snv_data.values())] = (snv, is_new)

                for dest in filter(bool, prot.split(',')):
                    name, refseq, exon, cdna_mut, prot_mut = dest.split(':')
                    assert refseq.startswith('NM_')
                    # refseq = int(refseq[3:])
                    # name and refseq are redundant with respect one to another

                    assert exon.startswith('exon')
                    exon = int(exon[4:])
                    assert cdna_mut.startswith('c.')

                    if (cdna_mut[2].lower() == ref and
                            cdna_mut[-1].lower() == alt):
                        strand = True
                    elif (complement(cdna_mut[2]).lower() == ref and
                          complement(cdna_mut[-1]).lower() == alt):
                        strand = False
                    else:
                        raise Exception(line)

                    cdna_pos = int(cdna_mut[3:-1])
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
                    aa_pos = int(prot_mut[3:-1])
                    aa_alt = prot_mut[-1]

                    try:
                        # try to get it from cache (`proteins` dictionary)
                        protein = proteins[refseq]
                        cnt_old_prots += 1
                        # if cache has been flushed, retrive from database
                        if not protein:
                            protein = Protein.query.filter_by(refseq=refseq).first()
                            proteins[refseq] = protein
                    except KeyError:
                        # if the protein was not in the cache,
                        # create it and add to the cache
                        print(
                            'Create protein from mappings:', refseq,
                            'it will not have any other data!'
                        )
                        # the gene and protein (if created) will be added
                        # to database by cascade run by adding CSVs
                        gene, _ = get_or_create(Gene, name=name)
                        protein = Protein(refseq=refseq, gene=gene)
                        proteins[refseq] = protein
                        cnt_new_prots += 1

                    csv = CodingSequenceVariant(
                        pos=aa_pos,
                        ref=aa_ref,
                        alt=aa_alt,
                        cdna_pos=cdna_pos,
                        exon=exon,
                        strand=strand,
                        protein=protein,
                        snv=snv
                    )

                    protein_muts.append(csv)

    db.session.add_all(protein_muts)
    db.session.commit()
    print('Read', len(files), 'files with genome -> protein mappings, ')
    print(cnt_new_prots, 'new proteins created & ', cnt_old_prots, 'used')
