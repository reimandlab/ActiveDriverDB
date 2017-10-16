from warnings import warn

from models import MIMPMutation
from imports.mutations import MutationImporter
from helpers.bioinf import decode_raw_mutation
from helpers.parsers import parse_tsv_file


class Importer(MutationImporter):
    # load("all_mimp_annotations_p085.rsav")
    # write.table(all_mimp_annotations, file="all_mimp_annotations.tsv",
    # row.names=F, quote=F, sep='\t')

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

    def parse(self, path):
        mimps = []

        def parser(line):
            nonlocal mimps

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
                self.broken_seq[refseq].append((protein.id, alt))
                return

            assert line[13] in ('gain', 'loss')

            # MIMP mutations are always hardcoded PTM mutations
            mutation_id = self.get_or_make_mutation(pos, protein.id, alt, True)

            psite_pos = int(psite_pos)

            affected_sites = [
                site
                for site in protein.sites
                if site.position == psite_pos
            ]

            if len(affected_sites) != 1:
                warning = UserWarning(
                    'MIMP site does not match to the database: ' +
                    (
                        'too many (%s) sites found. ' % len(affected_sites)
                        if affected_sites else
                        'given site not found. '
                    ) +
                    ' '.join(map(str, (
                        protein, refseq, ref, pos, alt, mutation_id, psite_pos
                    )))
                )
                print(warning)
                warn(warning)
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

        parse_tsv_file(path, parser, self.header)

        return mimps

    def insert_details(self, mimps):

        self.insert_list(mimps)
