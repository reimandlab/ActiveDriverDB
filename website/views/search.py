import json
from flask import render_template as template
from flask import request
from flask import jsonify
from flask import url_for
from flask_classful import FlaskView
from flask_classful import route
from Levenshtein import distance
from models import Protein
from models import Gene
from models import Mutation
from sqlalchemy import and_
from helpers.filters import FilterManager
from helpers.filters import Filter
from helpers.widgets import FilterWidget
from ._commons import get_genomic_muts
from ._commons import get_protein_muts


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

        sort_key = lambda gene: min(
            [
                distance(isoform.refseq, phase)
                for isoform in gene.isoforms
            ]
        )

    else:
        # if the phrase is not numeric
        sort_key = lambda gene: distance(gene.name, phase)

    return sorted(
        genes.values(),
        key=sort_key
    )


def parse_vcf(vcf_file, results, without_mutations, badly_formatted, data_filter):

    query = ''

    for line in vcf_file:
        line = line.decode('latin1')
        if line.startswith('#'):
            continue
        data = line.split()

        if len(data) < 5:
            if not line:    # if we reached end of the file
                break
            badly_formatted.append(line)
            continue

        chrom, pos, var_id, ref, alts = data[:5]

        if chrom.startswith('chr'):
            chrom = chrom[3:]

        alts = alts.split(',')
        for alt in alts:

            items = get_genomic_muts(chrom, pos, ref, alt)

            items = data_filter(items)

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
                        'user_input': parsed_line,
                        'results': items,
                        'count': 1
                    }
            else:
                without_mutations.append(parsed_line)

            query += parsed_line
    return query


def parse_text(
    textarea_query, results, without_mutations, badly_formatted, data_filter
):
    for line in textarea_query.split('\n'):
        data = line.split()
        if len(data) == 4:
            chrom, pos, ref, alt = data
            chrom = chrom[3:]

            items = get_genomic_muts(chrom, pos, ref, alt)

        elif len(data) == 2:
            gene, mut = [x.upper() for x in data]

            items = get_protein_muts(gene, mut)
        else:
            badly_formatted.append(line)
            continue

        items = data_filter(items)

        if items:
            if line in results:
                results[line]['count'] += 1
                assert results[line]['results'] == items
            else:
                results[line] = {
                    'user_input': line, 'results': items, 'count': 1
                }
        else:
            without_mutations.append(line)


def search_mutations(vcf_file, textarea_query, data_filter):
    # note: entries from both file and textarea will be merged
    query = ''

    results = {}
    without_mutations = []

    badly_formatted = []

    if vcf_file:
        query += parse_vcf(
            vcf_file, results, without_mutations, badly_formatted, data_filter
        )

    if textarea_query:
        query += textarea_query
        parse_text(
            textarea_query, results, without_mutations, badly_formatted, data_filter
        )

    return results, without_mutations, badly_formatted, query


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


def save_as_dataset(name, data, password=None):
    import pickle
    import os
    import base64
    from tempfile import NamedTemporaryFile

    os.makedirs('user_mutations', exist_ok=True)

    encoded_name = str(base64.urlsafe_b64encode(bytes(name, 'utf-8')), 'utf-8')

    db_file = NamedTemporaryFile(
        dir='user_mutations',
        prefix=encoded_name,
        suffix='.db',
        delete=False
    )
    pickle.dump(data, db_file, protocol=pickle.HIGHEST_PROTOCOL)

    uri_code = os.path.basename(db_file.name)[:-3]

    return uri_code


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

    def stored_mutations(self, code):
        import pickle
        import os
        from urllib.parse import unquote

        filter_manager = SearchViewFilters()

        filename = 'user_mutations/' + unquote(code) + '.db'
        print(filename)

        if os.path.exists(filename):
            with open(filename, 'rb') as f:
                results = pickle.load(f)
        else:
            return 'Nothing here :('

        return template(
            'search/index.html',
            target='mutations',
            results=results,
            widgets=make_widgets(filter_manager),
            without_mutations=[],
            query='',
            badly_formatted=[]
        )

    @route('/mutations', methods=['POST', 'GET'])
    def mutations(self):
        """Render search form and results (if any) for proteins or mutations"""

        without_mutations = []
        badly_formatted = []

        filter_manager = SearchViewFilters()

        if request.method == 'POST':
            from operator import itemgetter
            textarea_query = request.form.get('mutations', False)
            vcf_file = request.files.get('vcf-file', False)

            results, without_mutations, badly_formatted, query = search_mutations(
                vcf_file,
                textarea_query,
                lambda elements: filter_manager.apply(
                    elements,
                    itemgetter=itemgetter('mutation')
                )
            )

            store_on_server = request.form.get('store_on_server', False)

            if store_on_server:
                from flask import flash
                from urllib.parse import quote
                name = request.form.get('dataset_name', 'Custom Dataset')
                password = request.form.get('dataset_password', None)

                uri = save_as_dataset(name, results, password)

                uri = quote(uri)
                print(uri)
                url = url_for(
                    'SearchView:stored_mutations',
                    code=uri,
                    _external=True
                )

                flash(
                    'Your data have been saved on the server. '
                    'You can access the results later using following URL: '
                    '<a href="' + url + '">' + url + '</a>',
                    'success'
                )
        else:
            query = ''
            results = []

        return template(
            'search/index.html',
            target='mutations',
            results=results,
            widgets=make_widgets(filter_manager),
            without_mutations=without_mutations,
            query=query,
            badly_formatted=badly_formatted
        )

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
