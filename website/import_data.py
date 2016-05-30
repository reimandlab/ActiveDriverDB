from app import db
from models import Protein, Cancer, Mutation, Site
from collections import defaultdict


def import_data():

    proteins = {}

    with open('data/longest_isoform_proteins.fa', 'r') as f:

        name = None
        for line in f:
            if line.startswith('>'):
                name = line[1:].rstrip()
                assert name not in proteins
                protein = Protein(name)
                proteins[name] = protein
            else:
                proteins[name].sequence += line.rstrip()
    db.session.add_all(proteins.values())
    print('Sequences loaded')
    db.session.commit()

    with open('data/longest_isoforms.tsv', 'r') as f:
        header = f.readline().split('\t')
        for line in f:
            line = line.rstrip()
            name, refseq = line.split('\t')
            proteins[name].refseq = refseq
    print('Refseq ids loaded')
    db.session.commit()

    with open('data/longest_isoform_proteins_disorder.fa', 'r') as f:
        name = None
        for line in f:
            if line.startswith('>'):
                name = line[1:].rstrip()
                assert name in proteins
            else:
                proteins[name].disorder_map += line.rstrip()
    print('Disorder data loaded')
    db.session.commit()

    cancers = {}
    with open('data/cancer_types.txt', 'r') as f:
        for line in f:
            line = line.rstrip()
            code, name, color = line.split('\t')
            assert code not in cancers
            cancers[code] = Cancer(code, name)
    db.session.add_all(cancers.values())
    db.session.commit()

    print('Cancers loaded')

    mutations = defaultdict(list)
    with open('data/ad_muts.tsv', 'r') as f:
        header = f.readline().split('\t')
        for line in f:
            line = line.rstrip().split('\t')
            gene, _, sample_data, position, wt_residue, mut_residue = line
            _, _, cancer_code, sample_id, _, _ = sample_data.split(' ')

            mutation = Mutation(
                proteins[gene].id,
                cancers[cancer_code].id,
                sample_id,
                position,
                wt_residue,
                mut_residue
            )
            mutations[gene].append(mutation)

        for gene, gene_mutations in mutations.items():
            proteins[gene].mutations = gene_mutations
            db.session.add_all(gene_mutations)

    print('Mutations loaded')
    db.session.commit()

    with open('data/psite_table.tsv', 'r') as f:
        header = f.readline().split('\t')
        for line in f:
            line = line.rstrip()
            gene, position, residue, kinase, pmid = line.split('\t')
            site = Site(proteins[gene].id, position, residue, kinase, pmid)
            proteins[gene].sites.append(site)
    print('Protein sites loaded')
    db.session.commit()
