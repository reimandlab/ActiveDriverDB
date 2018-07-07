from datetime import datetime
import gzip
import os

from pandas import DataFrame
from sqlalchemy.orm import load_only
from tqdm import tqdm

from database import db, fast_count
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

    def iterate_export(self, only_preferred=False, mutation_filter=None, protein_filter=None, show_progress=True):
        """Yield tuples with mutations data prepared for export.

        A single mutation will be spread over multiple rows if it is necessary
        in order to keep columns with source-specific mutation details
        (like cancer_type or disease_name) atomic.

        Args:
            only_preferred: include only mutations from preferred isoforms of genes
            mutation_filter: SQLAlchemy filter for mutations
                (to be applied to joined self.model and Mutations tables)
            protein_filter: SQLAlchemy filter for proteins
            show_progress: wheter to show progress bar

        Returns:
            tuples with fields as returned by self.export_header
        """

        # cache preferred isoforms in a set (to enable fast access)
        preferred_isoforms = None

        if only_preferred:
            preferred_isoforms = set(i for i, in db.session.query(Gene.preferred_isoform_id))

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

            #ptms = ','.join({site_type.name for site in mut.affected_sites for site_type in site.types})
            for instance in export_details(mutation_details):
                yield (
                    gene_name_by_protein[protein], protein.refseq,
                    str(mut.position), ref, mut.alt, *instance
                )

    def export_to_df(self, only_preferred=False, mutation_filter=None, protein_filter=None, show_progress=True) -> DataFrame:
        """Export mutations to pandas.DataFrame. Arguments as in self.iterate_export."""

        mutations = [
            mutation
            for mutation in self.iterate_export(
                only_preferred=only_preferred,
                mutation_filter=mutation_filter,
                protein_filter=protein_filter,
                show_progress=show_progress
            )
        ]

        return DataFrame(mutations, columns=self.export_header)

    @property
    def export_header(self):
        return [
           'gene', 'isoform', 'position',  'wt_residue', 'mut_residue'
        ] + self.export_details_headers()

    def export(self, path=None, only_preferred=False):
        """Export all mutations from this source in ActiveDriver compatible format.

        Source specific data export can be implemented with export_details method,
        while export_details_headers should provide names for respective headers.
        """
        export_time = datetime.utcnow()

        if not path:
            directory = os.path.join('exported', 'mutations')
            os.makedirs(directory, exist_ok=True)

            name_template = '{model_name}{restrictions}-{date}.tsv.gz'

            name = name_template.format(
                model_name=self.model_name,
                restrictions=(
                    '-primary_isoforms_only' if only_preferred else ''
                ),
                date=export_time
            )
            path = os.path.join(directory, name)

        with gzip.open(path, 'wt') as f:

            f.write('\t'.join(self.export_header))

            for mutation_data in self.iterate_export(only_preferred=only_preferred):

                f.write('\n' + '\t'.join(mutation_data))
