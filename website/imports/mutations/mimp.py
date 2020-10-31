from warnings import warn

from models import MIMPMutation, SiteType
from helpers.bioinf import decode_raw_mutation
from helpers.parsers import tsv_file_iterator, count_lines_tsv

from .mutation_importer import ChunkedMutationImporter


class MIMPImporter(ChunkedMutationImporter):
    """
    As MIMP mutations are conditional on sites, these HAVE TO be imported after sites.
    """
    # load("all_mimp_annotations_p085.rsav")
    # write.table(all_mimp_annotations, file="all_mimp_annotations.tsv",
    # row.names=F, quote=F, sep='\t')

    name = 'mimp'
    model = MIMPMutation
    default_path = 'data/mutations/all_mimp_annotations.tsv'
    header = [
        'gene', 'mut', 'psite_pos', 'mut_dist', 'wt', 'mt', 'score_wt',
        'score_mt', 'log_ratio', 'pwm', 'pwm_fam', 'nseqs', 'prob', 'effect'
    ]
    insert_keys = (
        'mutation_id',
        'position_in_motif',
        'effect',
        'pwm',
        'pwm_family',
        'probability',
        'site_id'
    )
    site_type = 'phosphorylation'
    chunk_size = round(24227847 / 5)   # should be optimal for 8 GB of memory

    def iterate_lines(self, path):
        return tsv_file_iterator(path, self.header)

    def iterate_chunk(self, path, chunk_start, chunk_size):
        header = self.header if chunk_size == 0 else None
        return tsv_file_iterator(path, header, skip=chunk_start, limit=chunk_size)

    def count_lines(self, path) -> int:
        return count_lines_tsv(path)

    def parse_chunk(self, path, chunk_start, chunk_size):
        mimps = []
        site_type = SiteType.query.filter_by(name=self.site_type).one()
        skipped_predictions = 0
        mismatched_sequences = 0

        def parser(line):
            nonlocal mimps, skipped_predictions, mismatched_sequences

            refseq = line[0]
            mut = line[1]
            psite_pos = line[2]

            try:
                protein = self.proteins[refseq]
            except KeyError:
                return

            ref, pos, alt = decode_raw_mutation(mut)

            try:
                assert ref == protein.sequence[pos - 1]
            except (AssertionError, IndexError):
                mismatched_sequences += 1
                return

            assert line[13] in ('gain', 'loss')

            # MIMP mutations are always hardcoded PTM mutations
            mutation_id = self.get_or_make_mutation(pos, protein.id, alt, True)

            psite_pos = int(psite_pos)

            affected_sites = [
                site
                for site in protein.sites
                if site.position == psite_pos
                and any(t == site_type for t in site.types)
            ]

            # as this is site-type specific and only one site object of given type should be placed at a position,
            # we can should assume that the selection above will always produce less than two sites
            assert len(affected_sites) <= 1

            if not affected_sites:
                warning = UserWarning(
                    f'Skipping {refseq}: {ref}{pos}{alt} (for site at position {psite_pos}): '
                    'MIMP site does not match to the database - given site not found.'
                )
                warn(warning)
                skipped_predictions += 1
                return

            site_id = affected_sites[0].id

            mimps.append(
                (
                    mutation_id,
                    int(line[3]),
                    1 if line[13] == 'gain' else 0,
                    line[9],
                    line[10],
                    float(line[12]),
                    site_id
                )
            )

        for line in self.iterate_chunk(path, chunk_start, chunk_size):
            parser(line)

        if skipped_predictions:
            ratio = skipped_predictions / (skipped_predictions + len(mimps))
            print(f'In this chunk skipped {skipped_predictions} MIMP predictions ({ratio * 100}%)')

        print(f'Skipped {mismatched_sequences} mismatched sequences')

        return mimps

    def insert_details(self, mimps):

        self.insert_list(mimps)

    def export_details_headers(self):
        ignored = {'mutation_id', 'site_id'}
        return [key for key in self.insert_keys if key not in ignored]

    def export_details(self, mutation):
        return [
            [
                str(getattr(mutation, attr))
                for attr in self.export_details_headers()
            ]
        ]
