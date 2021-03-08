from collections import defaultdict
import gzip

from database import db
from database import get_or_create
from helpers.parsers import parse_tsv_file
from helpers.parsers import iterate_tsv_gz_file
from models import Protein
from models import ProteinReferences
from models import EnsemblPeptide
from models import UniprotEntry

from sqlalchemy.orm.exc import NoResultFound


class ReferencesParser:
    def __init__(self):
        self.references = defaultdict(list)

    ensembl_references_to_collect = {
        'Ensembl_PRO': 'peptide_id'
    }

    def add_uniprot_accession(self, data):
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
                isoform = None  # indicates "no isoform specified"

            reference, new = get_or_create(ProteinReferences, protein=protein)
            uniprot_entry, new_uniprot = get_or_create(UniprotEntry, accession=uniprot, isoform=isoform)
            reference.uniprot_entries.append(uniprot_entry)
            self.references[uniprot].append(reference)

            if new:
                db.session.add(reference)
            if new_uniprot:
                db.session.add(uniprot_entry)

    def add_references_by_uniprot(self, data):

        full_uniprot, ref_type, value = data

        if '-' in full_uniprot:
            uniprot, isoform = full_uniprot.split('-')
            uniprot_tied_references = self.references.get(uniprot, None)
            if not uniprot_tied_references:
                return

            relevant_references = []
            # select relevant references:
            for reference in uniprot_tied_references:
                if any(entry.isoform == int(isoform) for entry in reference.uniprot_entries):
                    relevant_references.append(reference)

        else:
            uniprot_tied_references = self.references.get(full_uniprot, None)
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
                    matching_entries = [entry for entry in reference.uniprot_entries if entry.accession == full_uniprot]
                    if len(matching_entries) != 1:
                        print(f'More than one match for reference: {reference}: {matching_entries}')
                    if not matching_entries:
                        print(f'No matching entries for reference: {reference}: {matching_entries}')
                        continue
                    entry = matching_entries[0]
                    entry.reviewed = True

            return

        if ref_type in self.ensembl_references_to_collect:

            attr = self.ensembl_references_to_collect[ref_type]

            for relevant_reference in relevant_references:
                attrs = {'reference': relevant_reference, attr: value}

                peptide, new = get_or_create(EnsemblPeptide, **attrs)

                if new:
                    db.session.add(peptide)

    def add_ncbi_mappings(self, data):
        # 9606    3329    HSPD1   NG_008915.1     NM_199440.1     NP_955472.1     reference standard
        taxonomy, entrez_id, gene_name, refseq_gene, lrg, refseq_nucleotide, t, refseq_peptide, p, category = data

        refseq_nm = refseq_nucleotide.split('.')[0]

        if not refseq_nm or not refseq_nm.startswith('NM'):
            return

        try:
            protein = Protein.query.filter_by(refseq=refseq_nm).one()
        except NoResultFound:
            return

        reference, new = get_or_create(ProteinReferences, protein=protein)

        if new:
            db.session.add(reference)

        reference.refseq_np = refseq_peptide.split('.')[0]
        reference.refseq_ng = refseq_gene.split('.')[0]
        gene = protein.gene

        if gene.name != gene_name:
            print(f'Gene name mismatch for RefSeq mappings: {gene.name} vs {gene_name}')

        entrez_id = int(entrez_id)

        if gene.entrez_id:
            if gene.entrez_id != entrez_id:
                print(f'Entrez ID mismatch for isoforms of {gene.name} gene: {gene.entrez_id}, {entrez_id}')
                if gene.name == gene_name:
                    print(
                        f'Overwriting {gene.entrez_id} entrez id with {entrez_id} for {gene.name} gene, '
                        f'because record with {entrez_id} has matching gene name'
                    )
                    gene.entrez_id = entrez_id
        else:
            gene.entrez_id = entrez_id

    def parse(
        self,
        path='data/HUMAN_9606_idmapping.dat.gz',
        refseq_lrg='data/LRG_RefSeqGene',
        refseq_link='data/refseq_link.tsv.gz'
    ):
        parse_tsv_file(refseq_lrg, self.add_ncbi_mappings, file_header=[
            '#tax_id', 'GeneID', 'Symbol', 'RSG', 'LRG', 'RNA', 't', 'Protein', 'p', 'Category'
        ])

        # add mappings retrieved from UCSC tables for completeness
        header = ['#name', 'product', 'mrnaAcc', 'protAcc', 'geneName', 'prodName', 'locusLinkId', 'omimId']
        for line in iterate_tsv_gz_file(refseq_link, header):
            gene_name, protein_full_name, refseq_nm, refseq_peptide, _, _, entrez_id, omim_id = line

            if not refseq_nm or not refseq_nm.startswith('NM'):
                continue

            try:
                protein = Protein.query.filter_by(refseq=refseq_nm).one()
            except NoResultFound:
                continue

            gene = protein.gene

            if gene.name != gene_name:
                print(f'Gene name mismatch for RefSeq mappings: {gene.name} vs {gene_name}')

            entrez_id = int(entrez_id)

            if protein_full_name:
                if protein.full_name:
                    if protein.full_name != protein_full_name:
                        print(
                            f'Protein full name mismatch: {protein.full_name} vs {protein_full_name} for {protein.refseq}'
                        )
                    continue
                protein.full_name = protein_full_name

            if gene.entrez_id:
                if gene.entrez_id != entrez_id:
                    print(f'Entrez ID mismatch for isoforms of {gene.name} gene: {gene.entrez_id}, {entrez_id}')
                    if gene.name == gene_name:
                        print(
                            f'Overwriting {gene.entrez_id} entrez id with {entrez_id} for {gene.name} gene, '
                            f'because record with {entrez_id} has matching gene name'
                        )
                        gene.entrez_id = entrez_id
            else:
                gene.entrez_id = entrez_id

            if refseq_peptide:
                reference, new = get_or_create(ProteinReferences, protein=protein)

                if new:
                    db.session.add(reference)

                if reference.refseq_np and reference.refseq_np != refseq_peptide:
                    print(
                        f'Refseq peptide mismatch between LRG and UCSC retrieved data: '
                        f'{reference.refseq_np} vs {refseq_peptide} for {protein.refseq}'
                    )

                reference.refseq_np = refseq_peptide

        parse_tsv_file(path, self.add_uniprot_accession, file_opener=gzip.open, mode='rt')
        parse_tsv_file(path, self.add_references_by_uniprot, file_opener=gzip.open, mode='rt')

        return [reference for reference_group in self.references.values() for reference in reference_group]
