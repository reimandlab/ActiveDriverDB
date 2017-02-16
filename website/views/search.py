import json
from operator import itemgetter
from flask import make_response
from flask import render_template as template
from flask import request
from flask import jsonify
from flask import url_for
from flask import flash
from flask import current_app
from flask_classful import FlaskView
from flask_classful import route
from flask_login import current_user
from Levenshtein import distance
from models import Protein
from models import Gene
from models import Mutation
from models import UsersMutationsDataset
from sqlalchemy import and_
from helpers.filters import FilterManager
from helpers.filters import Filter
from helpers.widgets import FilterWidget
from ._commons import get_genomic_muts
from ._commons import get_protein_muts
from database import db


class GeneResult:

    def __init__(self, gene, restrict_to_isoform=None):
        self.gene = gene
        if restrict_to_isoform:
            self.preffered_isoform = restrict_to_isoform

    def __getattr__(self, key):
        return getattr(self.gene, key)


def search_proteins(phase, limit=False, filter_manager=None):
    """Search for a protein isoform or gene.

    Limit means maximum results to be
    returned and will be applied to genes (so in the results there may be 10
    genes and 100 isoforms if the limit is equal to 10.
    """
    if not phase:
        return []

    # find by gene name
    filters = [Gene.name.like(phase + '%')]
    sql_filters = None

    if filter_manager:
        divided_filters = filter_manager.prepare_filters(Protein)
        sql_filters, manual_filters = divided_filters
        if manual_filters:
            raise ValueError(
                'From query can apply only use filters with'
                ' sqlalchemy interface'
            )

    if sql_filters:
        filters += sql_filters

    orm_query = (
        Gene.query
        .join(Protein, Protein.id == Gene.preferred_isoform_id)
        .filter(and_(*filters))
    )

    if limit:
        orm_query = orm_query.limit(limit)
    genes = {gene.name: GeneResult(gene) for gene in orm_query.all()}

    # looking up both by name and refseq is costly - perform it wisely
    if phase.isnumeric():
        phase = 'NM_' + phase
    if phase.startswith('NM_'):
        filters = [Protein.refseq.like(phase + '%')]
        if sql_filters:
            filters += sql_filters
        isoforms = Protein.query.filter(and_(*filters)).all()

        for isoform in isoforms:
            if limit and len(genes) > limit:
                break

            gene = isoform.gene

            if gene.name in genes:
                # add isoform to gene if
                if isoform not in genes[gene.name].isoforms:
                    genes[gene.name].isoforms.append(isoform)
            else:
                genes[gene.name] = GeneResult(gene, restrict_to_isoform=isoform)

        def sort_key(gene):
            return min(
                [
                    distance(isoform.refseq, phase)
                    for isoform in gene.isoforms
                ]
            )

    else:
        # if the phrase is not numeric
        def sort_key(gene):
            return distance(gene.name, phase)

    return sorted(
        genes.values(),
        key=sort_key
    )


class MutationSearch:

    def __init__(self, vcf_file=None, text_query=None, filter_manager=None):
        # note: entries from both file and textarea will be merged

        self.query = ''
        self.results = {}
        self.without_mutations = []
        self.badly_formatted = []

        if filter_manager:
            def data_filter(elements):
                return filter_manager.apply(
                    elements,
                    itemgetter=itemgetter('mutation')
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

    def parse_vcf(self, vcf_file):

        results = self.results

        for line in vcf_file:
            line = line.decode('latin1').strip()
            if line.startswith('#'):
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

                items = get_genomic_muts(chrom, pos, ref, alt)

                items = self.data_filter(items)

                chrom = 'chr' + chrom
                parsed_line = ' '.join((chrom, pos, ref, alt)) + '\n'

                if items:
                    if len(alts) > 1:
                        parsed_line += ' (' + alt + ')'

                    if parsed_line in results:
                        results[parsed_line]['count'] += 1
                        assert results[parsed_line]['results'] == items
                    else:
                        results[parsed_line] = {
                            'results': items,
                            'count': 1
                        }
                else:
                    self.without_mutations.append(parsed_line)

                self.query += parsed_line

    def parse_text(self, text_query):

        results = self.results

        for line in text_query.splitlines():
            data = line.strip().split()
            if len(data) == 4:
                chrom, pos, ref, alt = data
                chrom = chrom[3:]

                items = get_genomic_muts(chrom, pos, ref, alt)

            elif len(data) == 2:
                gene, mut = [x.upper() for x in data]

                items = get_protein_muts(gene, mut)
            else:
                self.badly_formatted.append(line)
                continue

            items = self.data_filter(items)

            if items:
                if line in results:
                    results[line]['count'] += 1
                    assert results[line]['results'] == items
                else:
                    results[line] = {
                        'results': items,
                        'count': 1
                    }
            else:
                self.without_mutations.append(line)


class SearchViewFilters(FilterManager):

    def __init__(self, **kwargs):
        filters = [
            # Why negation? Due to used widget: checkbox.
            # It is not possible to distinguish between user not asking for
            # all mutations (so sending nothing in post, since un-checking it
            # will cause it to be skipped in the form) or user doing nothing
            # (so expecting the default behavior - returning only PTM mutations)
            # - also no information present in the form.
            Filter(
                Mutation, 'is_ptm', comparators=['ne'],
                is_attribute_a_method=True,
                default=False
            ),
            Filter(
                Protein, 'has_ptm_mutations', comparators=['eq'],
                as_sqlalchemy=True
            )
        ]
        super().__init__(filters)
        self.update_from_request(request)


def make_widgets(filter_manager):
    return {
        'is_ptm': FilterWidget(
            'Show all mutations (by default only PTM mutations will be shown)',
            'checkbox',
            filter=filter_manager.filters['Mutation.is_ptm']
        ),
        'at_least_one_ptm': FilterWidget(
            'Show only proteins with PTM mutations', 'checkbox',
            filter=filter_manager.filters['Protein.has_ptm_mutations']
        )
    }


class SearchView(FlaskView):
    """Enables searching in any of registered database models."""

    def before_request(self, name, *args, **kwargs):
        filter_manager = SearchViewFilters()
        endpoint = self.build_route_name(name)

        return filter_manager.reformat_request_url(
            request, endpoint, *args, **kwargs
        )

    @route('/')
    def default(self):
        """Render default search form prompting to search for a protein."""
        return self.proteins()

    def proteins(self):
        """Render search form and results (if any) for proteins"""

        filter_manager = SearchViewFilters()

        query = request.args.get('proteins', '')

        results = search_proteins(query, 20, filter_manager)

        return template(
            'search/index.html',
            target='proteins',
            results=results,
            widgets=make_widgets(filter_manager),
            query=query
        )

    @route('saved/<uri>')
    def user_mutations(self, uri):

        filter_manager = SearchViewFilters()

        dataset = UsersMutationsDataset.query.filter_by(
            uri=uri
        ).one()

        if dataset.owner and dataset.owner.id != current_user.id:
            current_app.login_manager.unauthorized()

        response = make_response(template(
            'search/index.html',
            target='mutations',
            results=dataset.data.results,
            widgets=make_widgets(filter_manager),
            without_mutations=dataset.data.without_mutations,
            query=dataset.data.query,
            badly_formatted=dataset.data.badly_formatted,
            dataset=dataset
        ))
        return response

    @route('/mutations', methods=['POST', 'GET'])
    def mutations(self):
        """Render search form and results (if any) for proteins or mutations"""

        filter_manager = SearchViewFilters()

        if request.method == 'POST':
            textarea_query = request.form.get('mutations', False)
            vcf_file = request.files.get('vcf-file', False)

            mutation_search = MutationSearch(
                vcf_file,
                textarea_query,
                filter_manager
            )

            store_on_server = request.form.get('store_on_server', False)

            if store_on_server:
                name = request.form.get('dataset_name', 'Custom Dataset')

                if current_user.is_authenticated:
                    user = current_user
                else:
                    user = None
                    flash(
                        'To browse uploaded mutations easily in the '
                        'future, please register or log in with this form',
                        'warning'
                    )

                dataset = UsersMutationsDataset(
                    name=name,
                    data=mutation_search,
                    owner=user
                )

                db.session.add(dataset)
                db.session.commit()

                url = url_for(
                    'SearchView:user_mutations',
                    uri=dataset.uri,
                    _external=True
                )

                flash(
                    'Your mutations have been saved on the server. '
                    'You can access the results later using following URL: '
                    '<a href="' + url + '">' + url + '</a>',
                    'success'
                )
        else:
            mutation_search = MutationSearch()

        response = make_response(template(
            'search/index.html',
            target='mutations',
            results=mutation_search.results,
            widgets=make_widgets(filter_manager),
            without_mutations=mutation_search.without_mutations,
            query=mutation_search.query,
            badly_formatted=mutation_search.badly_formatted
        ))

        return response

    def form(self, target):
        """Return an empty HTML form appropriate for given target."""
        filter_manager = SearchViewFilters()
        return template(
            'search/forms/' + target + '.html',
            target=target,
            widgets=make_widgets(filter_manager)
        )

    def autocomplete_proteins(self, limit=20):
        """Autocompletion API for search for proteins."""

        filter_manager = SearchViewFilters()
        # TODO: implement on client side requests with limit higher limits
        # and return the information about available results (.count()?)
        query = request.args.get('q') or ''

        entries = search_proteins(query, limit, filter_manager)
        # page = request.args.get('page', 0)
        # Pagination(Pathway.query)
        # just pass pagination html too?

        response = {
            'query': query,
            'results': [
                {
                    'value': gene.name,
                    'html': template('search/results/gene.html', gene=gene)
                }
                for gene in entries
            ]
        }

        return jsonify(response)

    def autocomplete_searchbar(self, limit=6):
        """Autocompletion API for search for proteins (untemplated)."""
        query = request.args.get('q') or ''

        entries = search_proteins(query, limit)

        response = [
            gene.to_json()
            for gene in entries
        ]

        return json.dumps(response)
