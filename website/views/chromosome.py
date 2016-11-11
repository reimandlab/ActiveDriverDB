from flask import request
from flask_classful import FlaskView
from flask import jsonify
from models import Mutation
from website.helpers.filters import FilterManager
from website.views._global_filters import common_filters
from website.views._commons import get_genomic_muts
from website.views._commons import get_protein_muts
from website.views._commons import represent_mutations


class ChromosomeView(FlaskView):

    def _make_filters(self):
        filters = common_filters()
        filter_manager = FilterManager(filters)
        filter_manager.update_from_request(request)
        return filters, filter_manager

    def mutation(self, chrom, dna_pos, dna_ref, dna_alt):

        _, filter_manager = self._make_filters()

        if chrom.startswith('chr'):
            chrom = chrom[3:]

        items = get_genomic_muts(chrom, dna_pos, dna_ref, dna_alt)

        raw_mutations = filter_manager.apply([
            item['mutation'] for
            item in items
        ])

        parsed_mutations = represent_mutations(
            raw_mutations, filter_manager
        )

        return jsonify(parsed_mutations)

    def mutations(self, start, end):
        pass
