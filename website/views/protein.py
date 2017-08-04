from operator import attrgetter

from flask import jsonify
from flask import redirect
from flask import request
from flask import render_template as template
from flask import url_for
from flask_classful import route

from helpers.views import AjaxTableView
from models import Mutation
from models import Protein
from .abstract_protein import AbstractProteinView, get_raw_mutations
from .sequence import represent_needles, SequenceViewFilters, prepare_sites


class ProteinView(AbstractProteinView):
    """Single protein view: includes needleplot and sequence"""

    filter_class = SequenceViewFilters

    def show(self, refseq):
        return redirect(
            url_for('SequenceView:show', refseq=refseq) +
            '?' + request.query_string.decode('utf-8')
        )

    def index(self):
        """Show SearchView as default page"""
        return redirect(url_for('SearchView:default', target='proteins'))

    def browse(self):
        return template('protein/browse.html')

    browse_data = route('browse_data')(
        AjaxTableView.from_model(
            Protein,
            search_filter=(
                lambda q: Protein
                    .gene_name.remote_attr
                    .like(q + '%')
            ),
            sort='gene_name'
        )
    )

    def details(self, refseq):
        """Internal endpoint used for kinase tooltips"""
        protein, filter_manager = self.get_protein_and_manager(refseq)

        source = filter_manager.get_value('Mutation.sources')

        source_column = Mutation.source_fields[source]

        json = protein.to_json(data_filter=filter_manager.apply)

        meta = set()

        if source in ('1KGenomes', 'ESP6500'):
            summary_getter = attrgetter('affected_populations')
        else:
            def summary_getter(meta_column):
                return meta_column.summary()

        for mutation in filter_manager.apply(protein.mutations):
            meta_column = getattr(mutation, source_column)
            if not meta_column:
                continue
            meta.update(
                summary_getter(meta_column)
            )

        json['meta'] = list(meta)

        return jsonify(json)

    def mutation(self, refseq, position, alt):
        """REST API endpoint"""
        from .chromosome import represent_mutations
        from database import get_or_create

        protein, filter_manager = self.get_protein_and_manager(
            refseq,
            default_source=None,
            source_nullable=False
        )

        mutation, _ = get_or_create(
            Mutation,
            protein=protein,
            # setting id directly is easier than forcing update outside session
            protein_id=protein.id,
            position=int(position),
            alt=alt
        )

        raw_mutations = filter_manager.apply([mutation])

        assert len(raw_mutations) == 1

        if not raw_mutations:
            return jsonify(
                'There is a mutation, but it does not satisfy given filters'
            )

        parsed_mutations = represent_mutations(
            raw_mutations, filter_manager
        )

        return jsonify(parsed_mutations)

    def known_mutations(self, refseq):
        """REST API endpoint"""

        protein, filter_manager = self.get_protein_and_manager(refseq)

        raw_mutations = get_raw_mutations(protein, filter_manager)

        parsed_mutations = represent_needles(
            raw_mutations,
            filter_manager
        )

        return jsonify(parsed_mutations)

    def sites(self, refseq):
        """REST API endpoint"""

        protein, filter_manager = self.get_protein_and_manager(refseq)

        response = prepare_sites(protein, filter_manager)

        return jsonify(response)
