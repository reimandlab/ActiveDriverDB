from collections import defaultdict
from collections import OrderedDict
from database import db
from database import get_or_create
from helpers.bioinf import decode_mutation
from helpers.bioinf import decode_raw_mutation
from helpers.parsers import parse_tsv_file
from helpers.parsers import chunked_list
from helpers.parsers import read_from_files
from models import Cancer
from models import CancerMutation
from models import ExomeSequencingMutation
from models import MIMPMutation
from models import mutation_site_association
from models import Mutation
from models import The1000GenomesMutation
from models import InheritedMutation
from models import ClinicalData
from sqlalchemy.orm.exc import NoResultFound
from app import app


def load_mutations(proteins, removed):

    broken_seq = defaultdict(list)

    print('Loading mutations:')

    # a counter to give mutations.id as pk
    mutations_cnt = 1
    mutations = {}

    def flush_basic_mutations():
        nonlocal mutations
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
        mutations = {}

    def get_or_make_mutation(pos, protein_id, alt, is_ptm):
        nonlocal mutations_cnt, mutations

        key = (pos, protein_id, alt)
        if key in mutations:
            mutation_id = mutations[key][0]
        else:
            try:
                mutation = Mutation.query.filter_by(
                    position=pos, protein_id=protein_id, alt=alt
                ).one()
                mutation_id = mutation.id
            except NoResultFound:
                mutation_id = mutations_cnt
                mutations[key] = (mutations_cnt, is_ptm)
                mutations_cnt += 1
        return mutation_id

    def preparse_mutations(line):
        for mutation in [
            m.split(':')
            for m in line[9].replace(';', ',').split(',')
        ]:
            refseq = mutation[1]

            try:
                protein = proteins[refseq]
            except KeyError:
                continue

            ref, pos, alt = decode_mutation(mutation[4])

            try:
                assert ref == protein.sequence[pos - 1]
            except (AssertionError, IndexError):
                broken_seq[refseq].append((protein.id, alt))
                continue

            affected_sites = protein.get_sites_from_range(pos - 7, pos + 7)
            is_ptm = bool(affected_sites)

            mutation_id = get_or_make_mutation(pos, protein.id, alt, is_ptm)

            yield mutation_id

    def make_metadata_ordered_dict(keys, metadata, get_from=0):
        """Create an OrderedDict with given keys, and values

        extracted from metadata list (or beeing None if not present
        in metadata list. If there is a need to choose values among
        subfields (delimeted by ',') then get_from tells from which
        subfield the data should be used. This function will demand
        all keys existing in dictionary to be updated - if you want
        to loosen this requirement you can specify which fields are
        not compulsary, and should be assign with None value (as to
        import flags from VCF file).
        """
        dict_to_fill = OrderedDict(
            (
                (key, None)
                for key in keys
            )
        )

        for entry in metadata:
            try:
                # given entry is an assigment
                key, value = entry.split('=')
                if ',' in value:
                    value = float(value.split(',')[get_from])
            except ValueError:
                # given entry is a flag
                key = entry
                value = True

            if key in keys:
                dict_to_fill[key] = value

        return dict_to_fill

    # MIMP MUTATIONS

    # load("all_mimp_annotations_p085.rsav")
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

        assert line[13] in ('gain', 'loss')

        # MIMP mutations are always hardcoded PTM mutations
        mutation_id = get_or_make_mutation(pos, protein.id, alt, True)

        psite_pos = int(psite_pos)

        sites.extend([
            (site.id, mutation_id)
            for site in protein.sites
            if site.position == psite_pos
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

    parse_tsv_file('data/mutations/all_mimp_annotations.tsv', parser, header)

    flush_basic_mutations()

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

    engine = db.get_engine(app, 'bio')
    for chunk in chunked_list(sites):
        engine.execute(
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

    def cancer_parser(line):

        nonlocal mutations_counter

        assert line[10].startswith('comments: ')
        cancer_name, sample, _ = line[10][10:].split(';')

        cancer, created = get_or_create(Cancer, name=cancer_name)

        if created:
            db.session.add(cancer)

        for mutation_id in preparse_mutations(line):

            mutations_counter[
                (
                    mutation_id,
                    cancer.id,
                )
            ] += 1

    parse_tsv_file('data/mutations/TCGA_muts_annotated.txt', cancer_parser)

    flush_basic_mutations()

    for chunk in chunked_list(mutations_counter.items()):
        db.session.bulk_insert_mappings(
            CancerMutation,
            [
                {
                    'mutation_id': mutation[0],
                    'cancer_id': mutation[1],
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
    esp_mutations = []

    def esp_parser(line):

        metadata = line[20].split(';')

        # not flexible way to select MAF from metadata, but quite quick
        assert metadata[4].startswith('MAF=')

        maf_ea, maf_aa, maf_all = map(float, metadata[4][4:].split(','))

        for mutation_id in preparse_mutations(line):

            esp_mutations.append(
                (
                    maf_ea,
                    maf_aa,
                    maf_all,
                    mutation_id
                )
            )

    parse_tsv_file('data/mutations/ESP6500_muts_annotated.txt', esp_parser)

    flush_basic_mutations()

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

    # CLINVAR MUTATIONS
    print('Loading ClinVar mutations:')
    clinvar_mutations = []
    clinvar_data = []

    clinvar_keys = (
        'RS',
        'MUT',
        'VLD',
        'PMC',
        'CLNSIG',
        'CLNDBN',
        'CLNREVSTAT',
    )

    def clinvar_parser(line):

        metadata = line[20].split(';')

        clinvar_entry = make_metadata_ordered_dict(clinvar_keys, metadata)

        names, statuses, significances = (
            (entry.replace('|', ',').split(',') if entry else None)
            for entry in
            (
                clinvar_entry[key]
                for key in ('CLNDBN', 'CLNREVSTAT', 'CLNSIG')
            )
        )

        # those length should be always equal if they exists
        sub_entries_cnt = max([len(x) for x in (names, statuses, significances)])

        for i in range(sub_entries_cnt):

            try:
                if names:
                    if names[i] == 'not_specified':
                        names[i] = None
                    else:
                        names[i] = names[i].replace('\\x2c', ',').replace('_', ' ')
                if statuses and statuses[i] == 'no_criteria':
                    statuses[i] = None
            except IndexError:
                print('Malformed row (wrong count of subentries):')
                print(line)
                return False

        values = list(clinvar_entry.values())

        for mutation_id in preparse_mutations(line):

            clinvar_mutations.append(
                (
                    mutation_id,
                    # Python 3.5 makes it easy: **values, but is not avaialable
                    values[0],
                    values[1],
                    values[2],
                    values[3],
                )
            )

            for i in range(sub_entries_cnt):
                try:
                    clinvar_data.append(
                        (
                            len(clinvar_mutations),
                            significances[i] if significances else None,
                            names[i] if names else None,
                            statuses[i] if statuses else None,
                        )
                    )
                except:
                    print(significances, names, statuses, sub_entries_cnt)

    parse_tsv_file('data/mutations/clinvar_muts_annotated.txt', clinvar_parser)


    flush_basic_mutations()

    for chunk in chunked_list(clinvar_mutations):
        db.session.bulk_insert_mappings(
            InheritedMutation,
            [
                {
                    'mutation_id': mutation[0],
                    'db_snp_id': mutation[1],
                    'is_low_freq_variation': mutation[2],
                    'is_validated': mutation[3],
                    'is_in_pubmed_central': mutation[4],
                }
                for mutation in chunk
            ]
        )
        db.session.flush()

    db.session.commit()

    for chunk in chunked_list(clinvar_data):
        db.session.bulk_insert_mappings(
            ClinicalData,
            [
                {
                    'inherited_id': data[0],
                    'sig_code': data[1],
                    'disease_name': data[2],
                    'rev_status': data[3],
                }
                for data in chunk
            ]
        )
        db.session.flush()

    db.session.commit()


    # 1000 GENOMES MUTATIONS
    print('Loading 1000 Genomes mutations:')

    # TODO: there are some issues with this function
    def find_af_subfield_number(line):
        """Get subfield number in 1000 Genoms VCF-originating metadata,

        where allele frequencies for given mutations are located.

        Example record:
        10	73567365	73567365	T	C	exonic	CDH23	.	nonsynonymous SNV	CDH23:NM_001171933:exon12:c.T1681C:p.F561L,CDH23:NM_001171934:exon12:c.T1681C:p.F561L,CDH23:NM_022124:exon57:c.T8401C:p.F2801L	0.001398	100	20719	10	73567365	rs3802707	TC,G	100	PASS	AC=2,5;AF=0.000399361,0.000998403;AN=5008;NS=2504;DP=20719;EAS_AF=0.001,0.005;AMR_AF=0,0;AFR_AF=0,0;EUR_AF=0,0;SAS_AF=0.001,0;AA=T|||;VT=SNP;MULTI_ALLELIC;EX_TARGET	GT
        There are AF metadata for two different mutations: T -> TC and T -> G.
        The mutation which we are currently analysing is T -> C

        Look for fields 3 and 4; 4th field is sufficient to determine mutation.
        """
        dna_mut = line[4]
        return [seq[0] for seq in line[17].split(',')].index(dna_mut)

    thousand_genoms_mutations = []

    maf_keys = (
        'AF',
        'EAS_AF',
        'AMR_AF',
        'AFR_AF',
        'EUR_AF',
        'SAS_AF',
    )

    for line in read_from_files(
        'data/mutations/G1000',
        'G1000_chr*.txt.gz',
        skip_header=False
    ):
        line = line.rstrip().split('\t')

        metadata = line[20].split(';')

        maf_data = make_metadata_ordered_dict(
            maf_keys,
            metadata,
            find_af_subfield_number(line)
        )

        values = list(maf_data.values())

        for mutation_id in preparse_mutations(line):

            thousand_genoms_mutations.append(
                (
                    mutation_id,
                    # Python 3.5 makes it easy: **values, but is not avaialable
                    values[0],
                    values[1],
                    values[2],
                    values[3],
                    values[4],
                    values[5],
                )
            )

    flush_basic_mutations()

    for chunk in chunked_list(thousand_genoms_mutations):
        db.session.bulk_insert_mappings(
            The1000GenomesMutation,
            [
                dict(
                    zip(
                        (
                            'mutation_id',
                            'maf_all',
                            'maf_eas',
                            'maf_amr',
                            'maf_afr',
                            'maf_eur',
                            'maf_sas',
                        ),
                        mutation_metadata
                    )
                )
                for mutation_metadata in chunk
            ]
        )
        db.session.flush()

    db.session.commit()

    print('Mutations loaded')


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

            sites = protein.get_sites_from_range(aa_pos - 7, aa_pos + 7)

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
