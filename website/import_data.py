from app import db
from website.models import Protein, Cancer, Mutation, Site


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
        header = f.readline().split('\t')
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
        header = f.readline().split('\t')
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
        header = f.readline().split('\t')
        for line in f:
            line = line.rstrip()
            gene, position, residue, kinases, pmid = line.split('\t')
            kinases_names = filter(bool, kinases.split(','))
            kinases = []
            for name in kinases_names:
                try:
                    kinases.append(proteins[name])
                except:
                    print('No protein for kinase: ', name)
            Site(position, residue, pmid, proteins[gene], kinases)
    print('Protein sites loaded')
