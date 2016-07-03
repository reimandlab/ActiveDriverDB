from app import db
from website.models import Protein, Cancer, Mutation, Site, Kinase, KinaseGroup


def import_data():
    proteins = create_proteins_with_seq()
    load_protein_refseq(proteins)
    load_disorder(proteins)
    cancers = load_cancers()
    load_mutations(proteins, cancers)
    kinases, groups = load_sites(proteins)
    kinases, groups = load_kinase_classification(proteins, kinases, groups)
    db.session.add_all(kinases.values())
    db.session.add_all(groups.values())
    print('Added kinases')
    db.session.add_all(cancers.values())
    print('Added cancers')
    db.session.add_all(proteins.values())
    print('Added proteins')
    db.session.commit()


def create_proteins_with_seq():
    proteins = {}
    with open('data/longest_isoform_proteins.fa', 'r') as f:

        name = None
        for line in f:
            if line.startswith('>'):
                name = line[1:].rstrip()
                assert name not in proteins
                protein = Protein(name=name)
                proteins[name] = protein
            else:
                proteins[name].sequence += line.rstrip()
    print('Sequences loaded')
    return proteins


def load_protein_refseq(proteins):
    with open('data/longest_isoforms.tsv', 'r') as f:
        header = f.readline().rstrip().split('\t')
        assert header == ['gene', 'rseq']
        for line in f:
            line = line.rstrip()
            name, refseq = line.split('\t')
            proteins[name].refseq = refseq
    print('Refseq ids loaded')


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


class GenomicMutation:

    __slots__ = 'chr', 'pos', 'ref', 'alt'

    def __init__(self, chr, pos, ref, alt):
        self.chr = chr
        self.pos = pos
        self.ref = ref
        self.alt = alt


class ProteinMutation:

    __slots__ = 'pos', 'ref', 'alt', 'cdna_pos', 'exon', 'refseq', 'g', 'strand'

    def __init__(self, pos, ref, alt, cdna_pos, exon, refseq, g, strand):
        self.pos = pos
        self.ref = ref
        self.alt = alt
        self.cdna_pos = cdna_pos
        self.exon = exon
        # will be implemented with the foreginkey, and thetr will be a foreign
        # key to genomic mutation (with backref) or vice versa
        self.refseq = refseq
        self.g = g
        self.strand = strand


def import_mappings():

    files = get_files('data/200616/all_variants/playground', 'annot_*.txt.gz')

    genomic = []
    protein = []

    import gzip

    from helpers.bioinf import complement
    from helpers.bioinf import get_human_chromosomes

    chromosomes = get_human_chromosomes()

    for file in files:

        with gzip.open(file, 'rb') as f:
            next(f)  # skip the header
            for line in f:
                line = line.decode("latin1")
                chrom, pos, ref, alt, prot = line.rstrip().split('\t')
                assert chrom.startswith('chr')
                # with simple maping to ints we can
                chrom = chrom[3:]
                assert chrom in chromosomes
                ref, alt = map(ord, (ref, alt))
                pos = int(pos)

                g = GenomicMutation(chrom, pos, ref, alt)
                genomic.append(g)

                for dest in filter(bool, prot.split(',')):
                    name, refseq, exon, cdna_mut, prot_mut = dest.split(':')
                    assert refseq.startswith('NM_')
                    refseq = int(refseq[3:])
                    # name and refseq are redundant with respect one to another

                    assert exon.startswith('exon')
                    exon = int(exon[4:])
                    assert cdna_mut.startswith('c.')

                    if (ord(cdna_mut[2].lower()) == ref and
                            ord(cdna_mut[-1].lower()) == alt):

                        strand = 1
                    elif (ord(complement(cdna_mut[2]).lower()) == ref and
                          ord(complement(cdna_mut[-1]).lower()) == alt):
                        strand = -1
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

                    p = ProteinMutation(aa_pos, aa_ref, aa_alt, cdna_pos, exon,
                                        refseq, g, strand)
                    protein.append(p)

    print('Read', len(files), 'files with genome -> protein mappings')
    return genomic, protein
