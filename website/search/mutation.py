from collections import defaultdict
from operator import attrgetter
from typing import List

from werkzeug.datastructures import FileStorage

from app import celery
from database import bdb
from helpers.bioinf import complement
from models import UserUploadedMutation

from .mutation_result import SearchResult
from .protein_mutations import get_protein_muts


class MutationSearch:

    def __init__(self, vcf_file=None, text_query=None, filter_manager=None):
        """Performs search for known and novel mutations from provided VCF file and/or text query.

        Stop codon mutations are not considered.

        Args:
            vcf_file: a file object containing data in Variant Call Format
            text_query: a string of multiple lines, where each line represents either:
                 - a genomic mutation (e.g. chr12 57490358 C A) or
                 - a protein mutation (e.g. STAT6 W737C)
                Entries from both VCF file and text input will be merged.
            filter_manager: FilterManager instance used to filter out unwanted mutations
        """
        self.query = ''
        self.results = {}
        self.results_by_refseq = defaultdict(dict)
        self.without_mutations = []
        self.badly_formatted = []
        self.hidden_results_cnt = 0
        self._progress = 0
        self._total = 0
        if vcf_file:
            if type(vcf_file) is FileStorage:
                # as bad as it can be, but usually the vcf file will be a list of lines already
                vcf_file = vcf_file.readlines()
            self._total += len(vcf_file)
        if text_query:
            self._total += sum(1 for _ in text_query.splitlines())

        if filter_manager:
            def data_filter(elements):
                return filter_manager.apply(
                    elements,
                    itemgetter=attrgetter('mutation')
                )
        else:
            def data_filter(elements):
                return elements

        self.data_filter = data_filter

        if vcf_file:
            self.parse_vcf(vcf_file)

        if text_query:
            self.query += text_query
            self.parse_text(text_query)

        # when parsing is complete, quickly forget where is such complex object
        # like filter_manager so any instance of this class can be pickled.
        self.data_filter = None

    def progress(self):
        self._progress += 1
        if celery.current_task:
            celery.current_task.update_state(
                state='PROGRESS',
                meta={'progress': self._progress / self._total}
            )

    def add_mutation_items(self, items: List[SearchResult], query_line: str):

        self.progress()

        if not items:
            self.without_mutations.append(query_line)
            return False

        items = self.data_filter(items)

        if not items:
            self.hidden_results_cnt += 1
            return False

        if query_line in self.results:
            for result in self.results[query_line]:
                result.meta_user.count += 1
                mutation = result.mutation
                self.results_by_refseq[mutation.protein.refseq][mutation.position, mutation.alt] = result
        else:
            for result in items:
                mutation = result.mutation
                result.meta_user = UserUploadedMutation(
                    count=1,
                    query=query_line,
                    mutation=result.mutation
                )
                mutation.meta_user = result.meta_user
                self.results_by_refseq[mutation.protein.refseq][mutation.position, mutation.alt] = result
            self.results[query_line] = items

    def parse_vcf(self, vcf_file):

        for line in vcf_file:
            line = line.strip()
            if line.startswith('#') or line.startswith('Chr	Start'):
                continue
            data = line.split()

            if len(data) < 5:
                if not line:    # if we reached end of the file
                    break
                self.badly_formatted.append(line)
                continue

            chrom, pos, var_id, ref, alts = data[:5]

            if chrom.startswith('chr'):
                chrom = chrom[3:]

            alts = alts.split(',')
            for alt in alts:

                items = bdb.get_genomic_muts(chrom, pos, ref, alt)

                chrom = 'chr' + chrom
                parsed_line = ' '.join((chrom, pos, ref, alt)) + '\n'

                self.add_mutation_items(items, parsed_line)

                # we don't have queries in our format for vcf files:
                # those need to be built this way
                self.query += parsed_line

    def parse_text(self, text_query):
        complement_prefix = 'Complement of '

        for line in text_query.splitlines():
            if line.startswith(complement_prefix):
                line = line[len(complement_prefix):]
            data = line.strip().split()
            if len(data) == 4:
                chrom, pos, ref, alt = data
                if chrom.startswith('chr'):
                    chrom = chrom[3:]

                items = bdb.get_genomic_muts(chrom, pos, ref, alt)

                if not items:
                    line = complement_prefix + line
                    items = bdb.get_genomic_muts(chrom, pos, complement(ref), complement(alt))

            elif len(data) == 2:
                gene, mut = [x.upper() for x in data]

                items = get_protein_muts(gene, mut)
            else:
                self.badly_formatted.append(line)
                continue

            self.add_mutation_items(items, line)

