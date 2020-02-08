from itertools import permutations
from tempfile import NamedTemporaryFile
from typing import Dict

from analyses.gene_sets import gmt_from_domains
from database import db
from database_testing import DatabaseTest
from models import InterproDomain, Domain, Protein, Gene


class GeneSetTest(DatabaseTest):

    def test_domains(self):

        protein_data = [
            ('NM_000184', 'HBG2'),
            ('NM_000517', 'HBA2'),
            ('NM_024694', 'ADGB')
        ]
        proteins: Dict[str, Protein] = {}    # gene_name -> protein

        for refseq, gene_name in protein_data:
            g = Gene(name=gene_name)
            proteins[gene_name] = Protein(gene=g, refseq=refseq)

        sub_domain = InterproDomain(
            accession='IPR012292',
            description='Globin_dom',
            occurrences=[
                Domain(start=3, end=142, protein=proteins['HBA2']),
                Domain(start=784, end=869, protein=proteins['ADGB'])
            ]
        )

        domain = InterproDomain(
            accession='IPR009050',
            description='Globin-like',
            children=[sub_domain],
            occurrences=[
                Domain(start=3, end=147, protein=proteins['HBG2']),
                Domain(start=1, end=142, protein=proteins['HBA2'])
            ]
        )

        db.session.add_all([domain, sub_domain, *proteins.values()])

        with NamedTemporaryFile('w+') as f:

            gmt_from_domains(path=f.name, include_sub_types=True)

            accepted_lines = [
                'IPR009050\tGlobin-like\t' + '\t'.join(genes) + '\n'
                for genes in permutations(['HBA2', 'HBG2', 'ADGB'])
            ] + [
                'IPR012292\tGlobin_dom\t' + '\t'.join(genes) + '\n'
                for genes in permutations(['HBA2', 'ADGB'])
            ]
            gmt_lines = f.readlines()

            assert all(line in accepted_lines for line in gmt_lines)
            assert len(gmt_lines) == 2
