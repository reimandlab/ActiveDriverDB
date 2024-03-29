from datetime import datetime
import gzip
import os

from pandas import DataFrame
from sqlalchemy.orm import load_only
from tqdm import tqdm

from database import db
from helpers.patterns import abstract_property
from models import Gene, Protein, Mutation


class MutationExporter:

    @abstract_property
    def model(self):
        pass

    def export_details_headers(self):
        return []

    def export_details(self, mutation):
        return [],  # returns a tuple with empty list inside

    def iterate_export(self, only_preferred=False, mutation_filter=None, protein_filter=None):
        """Yield tuples with mutations data prepared for export.

        A single mutation will be spread over multiple rows if it is necessary
        in order to keep columns with source-specific mutation details
        (like cancer_type or disease_name) atomic.

        Args:
            only_preferred: include only mutations from preferred isoforms of genes
            mutation_filter: SQLAlchemy filter for mutations
                (to be applied to joined self.model and Mutations tables)
            protein_filter: SQLAlchemy filter for proteins

        Returns:
            tuples with fields as returned by self.export_header
        """

        # cache genes and proteins
        query = (
            db.session.query(Protein, Gene.name)
            .select_from(Protein)
            .options(load_only('sequence', 'refseq'))
            .join(Gene, Protein.gene_id == Gene.id)
            .filter(protein_filter if protein_filter is not None else True)
            .filter(Protein.is_preferred_isoform if only_preferred is not False else True)
        )

        gene_name_by_protein = {
            protein: gene_name
            for protein, gene_name in tqdm(query, total=query.count())
        }

        export_details = self.export_details

        query = (
            db.session.query(self.model, Mutation)
            .select_from(self.model)
            .join(Mutation)
            .join(Protein)
            .filter(protein_filter if protein_filter is not None else True)
            .filter(Protein.is_preferred_isoform if only_preferred is not False else True)
        )

        if mutation_filter is not None:
            query = query.filter(mutation_filter)

        total = query.count()

        for mutation_details, mut in tqdm(query, total=total):

            protein = mut.protein

            try:
                ref = mut.ref
            except IndexError:
                print(
                    f'Mutation: {protein.refseq} {mut.position}{mut.alt} '
                    f'is exceeding the proteins sequence'
                )
                ref = ''

            for instance in export_details(mutation_details):
                yield (
                    gene_name_by_protein[protein], protein.refseq,
                    str(mut.position), ref, mut.alt, *instance
                )

    def export_to_df(self, only_preferred=False, mutation_filter=None, protein_filter=None) -> DataFrame:
        """Export mutations to pandas.DataFrame. Arguments as in self.iterate_export."""

        mutations = [
            mutation
            for mutation in self.iterate_export(
                only_preferred=only_preferred,
                mutation_filter=mutation_filter,
                protein_filter=protein_filter
            )
        ]

        return DataFrame(mutations, columns=self.export_header)

    @property
    def export_header(self):
        return [
            'gene', 'isoform', 'position', 'wt_residue', 'mut_residue'
        ] + self.export_details_headers()

    def generate_export_path(self, only_preferred, prefix=''):
        export_time = datetime.utcnow()

        directory = os.path.join('exported', 'mutations')
        os.makedirs(directory, exist_ok=True)

        name_template = '{prefix}{model_name}{restrictions}_{date}.tsv.gz'

        name = name_template.format(
            prefix=prefix,
            model_name=self.model_name,
            restrictions=(
                '-primary_isoforms_only' if only_preferred else ''
            ),
            date=export_time.strftime('%Y-%m-%d_%H-%M')
        )
        return os.path.join(directory, name)

    def export(self, path=None, only_primary_isoforms=False, only_confirmed_mutations=True):
        """Export all mutations from this source in ActiveDriver compatible format.

        Source specific data export can be implemented with export_details method,
        while export_details_headers should provide names for respective headers.
        """

        if not path:
            path = self.generate_export_path(only_primary_isoforms)

        with gzip.open(path, 'wt') as f:

            f.write('\t'.join(self.export_header))

            mutation_filter = None
            if only_confirmed_mutations:
                mutation_filter = Mutation.is_confirmed

            for mutation_data in self.iterate_export(
                only_preferred=only_primary_isoforms,
                mutation_filter=mutation_filter
            ):

                f.write('\n' + '\t'.join(mutation_data))
