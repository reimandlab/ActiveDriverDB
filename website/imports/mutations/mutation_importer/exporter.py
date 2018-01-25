from datetime import datetime
import gzip
import os

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

    def iterate_export(self, only_preferred=False):

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
        )

        gene_name_by_protein = {
            protein: gene_name
            for protein, gene_name in tqdm(query, total=query.count())
        }

        export_details = self.export_details

        query = db.session.query(self.model, Mutation).select_from(self.model).join(Mutation)

        for mutation_details, mut in tqdm(query, total=fast_count(db.session.query(self.model))):

            protein = mut.protein

            if only_preferred and protein.id not in preferred_isoforms:
                continue

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

    def export_to_df(self, only_preferred=False):
        from pandas import DataFrame

        mutations = [
            mutation
            for mutation in self.iterate_export(only_preferred=only_preferred)
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
