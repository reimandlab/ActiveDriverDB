from app import db
from website.models import Protein, Cancer, Mutation, Site, Kinase


def import_data():
    proteins = create_proteins_with_seq()
    load_protein_refseq(proteins)
    load_disorder(proteins)
    cancers = load_cancers()
    load_mutations(proteins, cancers)
    load_sites(proteins)
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
            cancers[code] = Cancer(code, name)
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


def load_sites(proteins):
    with open('data/psite_table.tsv', 'r') as f:
        header = f.readline().rstrip().split('\t')
        assert header == ['gene', 'position', 'residue', 'kinase', 'pmid']
        kinases = {}
        for line in f:
            line = line.rstrip()
            gene, position, residue, kinases_str, pmid = line.split('\t')
            site_kinases = []
            for name in filter(bool, kinases_str.split(',')):
                if name not in kinases:
                    kinases[name] = Kinase(
                        name=name,
                        protein=proteins.get(name, None),
                        is_group=name.endswith('_GROUP')
                    )
                site_kinases.append(kinases[name])
            Site(position, residue, pmid, proteins[gene], site_kinases)
    print('Protein sites loaded')
