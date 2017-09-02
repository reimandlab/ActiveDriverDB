import json
from operator import itemgetter
from urllib.parse import unquote

from flask import make_response, redirect, abort
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
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.datastructures import FileStorage

from app import celery
from helpers.bioinf import complement
from models import Protein, Pathway, Cancer, GeneList, MC3Mutation, Disease, InheritedMutation, ClinicalData
from models import Gene
from models import Mutation
from models import UsersMutationsDataset
from models import UserUploadedMutation
from sqlalchemy import and_, exists, or_, text
from helpers.filters import FilterManager, quote_if_needed
from helpers.filters import Filter
from helpers.widgets import FilterWidget
from views.gene import prepare_subqueries
from ._commons import get_protein_muts
from database import db, levenshtein_sorted, bdb


class GeneResult:

    def __init__(self, gene, matched_isoforms=None):
        self.gene = gene
        if not matched_isoforms:
            matched_isoforms = []
        self.matched_isoforms = matched_isoforms

    def __getattr__(self, key):
        return getattr(self.gene, key)


def search_proteins(phase, limit=None, filter_manager=None):
    """Search for a protein isoform or gene.
    Only genes which have a primary isoforms will be returned.
    The query phrase will be trimmed on both ends as we do not
    expect HGNC gene names nor RefSeq ids to contain spaces.

    Args:
        'limit': number of genes to be returned (for limit=10 there
                 may be 100 -or more- isoforms and 10 genes returned)
    """
    phase = phase.strip()

    if not phase:
        return []

    # find by gene name
    filters = [Gene.name.like(phase + '%')]
    sql_filters = None

    if filter_manager:
        divided_filters = filter_manager.prepare_filters(Protein)
        sql_filters, manual_filters, required_joins = divided_filters
        if manual_filters:
            raise ValueError(
                'From query can apply only use filters with'
                ' sqlalchemy interface'
            )

    if sql_filters:
        filters += sql_filters

    orm_query = (
        Gene.query
        # join with proteins so PTM filter can be applied
        .join(Protein, Gene.preferred_isoform)
        .filter(and_(*filters))
    )

    if limit:
        orm_query = orm_query.limit(limit)

    genes = {gene.name: GeneResult(gene) for gene in orm_query}

    # looking up both by name and refseq is costly - perform it wisely
    if phase.isnumeric():
        phase = 'NM_' + phase
    if phase.startswith('NM_') or phase.startswith('nm_'):

        # TODO: tests for lowercase
        filters = [Protein.refseq.like(phase + '%')]

        if sql_filters:
            filters += sql_filters

        query = Protein.query.filter(and_(*filters))

        if limit:
            # we want to display up to 'limit' genes;
            # still it would be good to restrict isoforms
            # query in such way then even when getting
            # results where all isoforms match the same
            # gene it still provides more than one gene
            query = query.limit(limit * 20)

        for isoform in query:
            if limit and len(genes) > limit:
                break

            gene = isoform.gene

            # add isoform to promoted (matched) isoforms of the gene
            if gene.name in genes:
                if isoform not in genes[gene.name].matched_isoforms:
                    genes[gene.name].matched_isoforms.add(isoform)
            else:
                genes[gene.name] = GeneResult(gene, matched_isoforms={isoform})

        def sort_key(gene):
            return min(
                [
                    distance(isoform.refseq, phase)
                    for isoform in gene.matched_isoforms
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

    def progress(self):
        self._progress += 1
        if celery.current_task:
            celery.current_task.update_state(
                state='PROGRESS',
                meta={'progress': self._progress / self._total}
            )

    def add_mutation_items(self, items, query_line):

        self.progress()

        if not items:
            self.without_mutations.append(query_line)
            return False

        items = self.data_filter(items)

        if not items:
            self.hidden_results_cnt += 1
            return False

        if query_line in self.results:
            for item in self.results[query_line]:
                item['mutation'].meta_user.count += 1
        else:
            for item in items:
                item['mutation'].meta_user = UserUploadedMutation(
                    count=1,
                    query=query_line
                )
            self.results[query_line] = items

    def parse_vcf(self, vcf_file):

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

                items = bdb.get_genomic_muts(chrom, pos, ref, alt)

                chrom = 'chr' + chrom
                parsed_line = ' '.join((chrom, pos, ref, alt)) + '\n'

                self.add_mutation_items(items, parsed_line)

                # we don't have queries in our format for vcf files:
                # those need to be built this way
                self.query += parsed_line

    def parse_text(self, text_query):

        for line in text_query.splitlines():
            data = line.strip().split()
            if len(data) == 4:
                chrom, pos, ref, alt = data
                chrom = chrom[3:]

                items = bdb.get_genomic_muts(chrom, pos, ref, alt)

            elif len(data) == 2:
                gene, mut = [x.upper() for x in data]

                items = get_protein_muts(gene, mut)
            else:
                self.badly_formatted.append(line)
                continue

            self.add_mutation_items(items, line)


class SearchViewFilters(FilterManager):

    def __init__(self, **kwargs):
        filters = [
            # Why default = False? Due to used widget: checkbox.
            # It is not possible to distinguish between user not asking for
            # all mutations (so sending nothing in post, since un-checking it
            # will cause it to be skipped in the form) or user doing nothing

            # Why or? Take a look on table:
            # is_ptm    show all muts (by default only ptm)     include?
            # 0         0                                       0
            # 0         1                                       1
            # 1         0                                       1
            # 1         1                                       1
            Filter(
                Mutation, 'is_ptm', comparators=['or'],
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
            'Show all mutations (by default only PTM mutations are shown)',
            'checkbox',
            filter=filter_manager.filters['Mutation.is_ptm']
        ),
        'at_least_one_ptm': FilterWidget(
            'Show only proteins with PTM mutations', 'checkbox',
            filter=filter_manager.filters['Protein.has_ptm_mutations']
        )
    }


@celery.task
def search_task(vcf_file, textarea_query, filter_manager, dataset_uri=None):
    mutation_search = MutationSearch(vcf_file, textarea_query, filter_manager)
    return mutation_search, dataset_uri


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

    @route('saved/<path:uri>')
    def user_mutations(self, uri):

        filter_manager = SearchViewFilters()

        dataset = UsersMutationsDataset.by_uri(uri)

        if dataset.owner and dataset.owner != current_user:
            current_app.login_manager.unauthorized()

        response = make_response(template(
            'search/dataset.html',
            results=dataset.data.results,
            widgets=make_widgets(filter_manager),
            without_mutations=dataset.data.without_mutations,
            query=dataset.data.query,
            badly_formatted=dataset.data.badly_formatted,
            dataset=dataset
        ))
        return response

    @route('remove_saved/<path:uri>')
    def remove_user_mutations(self, uri):

        dataset = UsersMutationsDataset.by_uri(uri)
        name = dataset.name

        if not dataset.owner or dataset.owner != current_user:
            current_app.login_manager.unauthorized()

        try:
            dataset.remove()
        except Exception as e:
            message = 'Failed to remove dataset <b>%s</b> (%s).' % (name, uri)
            print(message, e)
            message += '<br>If the message reappears, please contact us.'
            flash(message, category='danger')
            raise abort(500)

        flash('Successfully removed <b>%s</b> dataset.' % name, category='success')
        return redirect(url_for('ContentManagementSystem:my_datasets'))

    def progress(self, task_id):

        celery_task = celery.AsyncResult(task_id)
        status = celery_task.status

        if status == 'SUCCESS':
            mutation_search, dataset_uri = celery_task.result
            if dataset_uri:
                dataset = UsersMutationsDataset.query.filter_by(uri=dataset_uri).one()
                dataset.data = mutation_search
            return redirect(url_for('SearchView:mutations', task_id=task_id))

        progress = celery_task.result.get('progress', 0) if status == 'PROGRESS' else 0

        return make_response(template(
            'search/progress.html',
            task=celery_task,
            progress=int(progress * 100),
            status=status
        ))

    @route('/mutations', methods=['POST', 'GET'])
    def mutations(self):
        """Render search form and results (if any) for proteins or mutations"""
        task_id = request.args.get('task_id', None)
        use_celery = current_app.config.get('USE_CELERY', False)
        filter_manager = SearchViewFilters()

        if request.method == 'POST':
            textarea_query = request.form.get('mutations', False)
            vcf_file = request.files.get('vcf-file', False)
            store_on_server = request.form.get('store_on_server', False)

            if not use_celery:
                mutation_search = MutationSearch(vcf_file, textarea_query, filter_manager)

            if store_on_server:
                name = request.form.get('dataset_name', None)
                if not name:
                    name = 'Custom Dataset'

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
                    data=mutation_search if not use_celery else None,
                    owner=user
                )

                db.session.add(dataset)
                db.session.commit()

            if use_celery:
                mutation_search = search_task.delay(
                    # vcf_file is not serializable but list of lines is
                    vcf_file.readlines() if vcf_file else None,
                    textarea_query,
                    filter_manager,
                    dataset.uri if store_on_server else None
                )

                return redirect(url_for('SearchView:progress', task_id=mutation_search.task_id))

        elif task_id:
            celery_task = celery.AsyncResult(task_id)
            mutation_search, dataset_uri = celery_task.result
            if dataset_uri:
                url = url_for(
                    'SearchView:user_mutations',
                    uri=dataset_uri,
                    _external=True
                )

                flash(
                    'Your mutations have been saved on the server.'
                    '<p>You can access the results later using following URL: '
                    '<a href="' + url + '">' + url + '</a></p>',
                    'success'
                )

            for items in mutation_search.results.values():
                for item in items:
                    db.session.add(item['mutation'])
        else:
            mutation_search = MutationSearch()

        response = make_response(template(
            'search/index.html',
            target='mutations',
            hidden_results_cnt=mutation_search.hidden_results_cnt,
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
        # TODO: implement on client side pagination?
        query = unquote(request.args.get('q')) or ''

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

    def anything(self):
        query = unquote(request.args.get('query')) or ''
        if ' ' in query:
            return redirect(url_for('SearchView:mutations', mutations=query))
        else:
            return redirect(url_for('SearchView:proteins', proteins=query))

    def autocomplete_all(self):
        """
        Supports:
            Protein or gene:
            {refseq_id}
            {gene}

            Mutation:
            {gene} {ref}{pos}{alt}
            {chr} {pos} {ref} {alt}

            Pathway:
            {pathway}
            GO:{pathway_gene_ontology_id}
            REAC:{pathway_reactome_id}

            Genes with mutations detected in cancer samples:
            {cancer name} -> cancer genes list

            Proteins with mutations related to given disease:
            {disease} -> clinvar gene list
            {disease} in {protein} -> sequence view
        """

        query = unquote(request.args.get('q')) or ''

        items = []

        if ' ' in query or query.upper().startswith('CHR'):
            # TODO: use exceptions for messaging control?
            mutation_result = autocomplete_mutation(query)
            if type(mutation_result) is tuple:
                mutations, are_there_more_muts = mutation_result
                items.extend(mutations)
                if are_there_more_muts:
                    items.append({
                        'type': 'see_more',
                        'name': 'Show all mutations matching <i>%s</i>' % query,
                        'url': url_for('SearchView:mutations', mutations=query)
                    })
            else:
                items.extend(mutation_result)

        if ' ' in query:
            genes, are_there_more_genes = autocomplete_gene(query, limit=2)
        else:
            genes, are_there_more_genes = autocomplete_gene(query, limit=3)

        items.extend(genes)
        if are_there_more_genes:
            items.append({
                'type': 'see_more',
                'name': 'Show all genes matching <i>%s</i>' % query,
                'url': url_for('SearchView:proteins', proteins=query)
            })

        pathways = suggest_matching_pathways(query)

        cancers = suggest_matching_cancers(query)

        diseases = suggest_matching_diseases(query)
        items.extend(diseases)

        items.extend(pathways)
        items.extend(cancers)

        return json.dumps({'entries': items})


def suggest_matching_cancers(query, count=2):
    cancers = levenshtein_sorted(Cancer.query.filter(
        or_(
            Cancer.code.ilike(query + '%'),
            Cancer.name.ilike('%' + query + '%'),
        )
    ), Cancer.name, query).limit(count)

    tcga_list = GeneList.query.filter_by(mutation_source_name=MC3Mutation.name).one()

    return [
        {
            'name': cancer.name,
            'code': cancer.code,
            'type': 'cancer',
            'url': url_for(
                'GeneView:list',
                list_name=tcga_list.name,
                filters=(
                    'Mutation.sources:in:%s' % tcga_list.mutation_source_name
                    +
                    ';Mutation.mc3_cancer_code:in:%s' % cancer.code
                )
            )
        }
        for cancer in cancers
    ]


def suggest_matching_diseases(q, count=3):

    items = []

    potential_disease = None

    if q.endswith(' i'):
        potential_disease = q[:-2]
    if q.endswith(' '):
        potential_disease = q[:-1]

    if potential_disease:
        disease = (
            levenshtein_sorted(
                Disease.query.filter(Disease.name.ilike('%' + potential_disease + '%')),
                Disease.name,
                potential_disease
            )
         ).first()
        if disease:
            return json_message(
                'Do you wish to search for <i>%s</i> mutations? '
                'Please specify gene, using: <code>{disease} in {gene}</code> schema'
                % disease.name
            )

    if q.endswith(' in'):
        q += ' '

    if ' in ' in q:
        disease_name, protein_name = q.split(' in ')

        if protein_name.isnumeric():
            protein_name = 'NM_' + protein_name

        disease_like = Disease.name.ilike('%' + disease_name + '%')
        disease = Disease.query.filter(disease_like).first()

        if disease:
            muts, _, _, = prepare_subqueries(
                [
                    disease_like,
                    ClinicalData.sig_code.in_(ClinicalData.significance_codes.keys()),
                    Mutation.is_confirmed == True
                ],
                [[InheritedMutation, ClinicalData, Disease]]
            )

            query = (
                db.session.query(
                    Disease.name,
                    Gene.name,
                    Protein.refseq,
                    muts
                )
                .select_from(Gene)
                .join(Protein, Protein.id == Gene.preferred_isoform_id)
                .join(Mutation, Mutation.protein_id == Protein.id)
                .join(InheritedMutation).join(ClinicalData).join(Disease).
                filter(disease_like)
            )
            if protein_name.upper().startswith('NM_'):
                query = query.filter(Protein.refseq.ilike(protein_name + '%'))
            else:
                query = query.filter(Gene.name.ilike('%' + protein_name + '%'))

            query = query.group_by(Gene).having(text('muts_cnt > 0'))

            query = levenshtein_sorted(query, Disease.name, disease_name)

            query = query.limit(count)

            items += [
                {
                    'name': disease,
                    'gene': gene,
                    'refseq': refseq,
                    'type': 'disease_in_protein',
                    'url': url_for(
                        'SequenceView:show',
                        refseq=refseq,
                        filters=(
                            'Mutation.sources:in:%s' % InheritedMutation.name
                            +
                            ';Mutation.disease_name:in:%s' % quote_if_needed(disease)
                        )
                    )
                }
                for disease, gene, refseq, muts in query
            ]

    diseases = levenshtein_sorted(Disease.query.filter(
        or_(
            Disease.name.ilike('%' + q + '%'),
        )
    ), Disease.name, q).limit(count)

    clinvar_list = GeneList.query.filter_by(mutation_source_name=InheritedMutation.name).first()

    items += [
        {
            'name': disease.name,
            'type': 'disease',
            'url': url_for(
                'GeneView:list',
                list_name=clinvar_list.name,
                filters=(
                    'Mutation.sources:in:%s' % clinvar_list.mutation_source_name
                    +
                    ';Mutation.disease_name:in:%s' % quote_if_needed(disease.name)
                )
            )
        }
        for disease in diseases
    ]

    return items


def suggest_matching_pathways(query, count=2):
    go = reactome = None

    if query.startswith('GO:'):
        go = query[3:]
        pathway_filter = Pathway.gene_ontology.like(go + '%')
        column = Pathway.gene_ontology
    elif query.startswith('REAC:'):
        reactome = query[5:]
        pathway_filter = Pathway.reactome.like(reactome + '%')
        column = Pathway.reactome
    else:
        pathway_filter = Pathway.description.like('%' + query + '%')
        column = Pathway.description

    pathways = Pathway.query.filter(pathway_filter)
    pathways = levenshtein_sorted(pathways, column, query)

    pathways = pathways.limit(count + 1).all()

    # show {count} of pathways; if we got {count} + 1 results suggest searching for all

    def display_name(pathway):
        name = pathway.description
        if go:
            name += ' (GO:%s)' % pathway.gene_ontology
        if reactome:
            name += ' (REAC:%s)' % pathway.reactome

        return name

    items = [
        {
            'name': display_name(pathway),
            'type': 'pathway',
            'gene_ontology': pathway.gene_ontology,
            'reactome': pathway.reactome,
            'url': url_for('PathwaysView:show', gene_ontology_id=pathway.gene_ontology, reactome_id=pathway.reactome)
        }
        for pathway in pathways[:count]
    ]
    if len(pathways) > count:
        items.append(
            {
                'name': 'Show all pathways matching <i>%s</i>' % query,
                'type': 'see_more',
                'url': url_for('PathwaysView:all', query=query)
            }
        )
    return items


def gene_exists(name):
    return db.session.query(exists().where(Gene.name == name)).scalar()


def json_message(msg):
    return [{'name': msg, 'type': 'message'}]


def autocomplete_gene(query, limit=5):
    """Returns: (autocompletion_gene_results, are_there_more)"""
    entries = search_proteins(query, limit + 1)
    items = [
        gene.to_json()
        for gene in entries
    ]
    for item in items:
        item['type'] = 'gene'

    return items[:limit], len(entries) > limit


def match_aa_mutation(gene, mut, query):
    import re
    try:
        gene_obj = Gene.query.filter_by(name=gene).one()
    except NoResultFound:
        # return json_message('No isoforms for %s found' % gene)
        return []

    all_parts = re.fullmatch('(?P<ref>\D)(?P<pos>(\d)+)(?P<alt>\D)', mut)
    ref_and_pos = re.fullmatch('(?P<ref>\D)(?P<pos>(\d)+)', mut)

    if all_parts:
        mut_data = all_parts.groupdict()

    if ref_and_pos:
        mut_data = ref_and_pos.groupdict()

    if all_parts or ref_and_pos:
        ref = mut_data['ref']
        try:
            pos = int(mut_data['pos'])
        except ValueError:
            return json_message(
                'Did you mean to search for mutation with <code>{gene} {ref}{pos}{alt}</code> format?'
                ' The <code>{pos}</code> should be an integer.'
            )

        # validate if ref is correct
        valid = False
        for isoform in gene_obj.isoforms:
            try:
                if isoform.sequence[pos - 1] == ref:
                    valid = True
                    break
            except IndexError:
                # not in range of this isoform, nothing scary.
                pass

        if not valid:
            return json_message(
                'Given reference residue <code>%s</code> does not match any of %s isoforms of %s gene at position <code>%s</code>'
                %
                (ref, len(gene_obj.isoforms), gene, pos)
            )

    if ref_and_pos:
        # if ref is correct and ask user to specify alt
        return json_message('Awaiting for <code>{alt}</code> - expecting mutation in <code>{gene} {ref}{pos}{alt}</code> format')

    only_ref = re.fullmatch('(?P<ref>\D)', mut)
    if only_ref:
        # prompt user to write more
        return json_message('Awaiting for <code>{pos}{alt}</code> - expecting mutation in <code>{gene} {ref}{pos}{alt}</code> format')

    try:
        items = get_protein_muts(gene, mut)
    except ValueError:
        return json_message(
            'Did you mean to search for mutation with <code>{gene} {ref}{pos}{alt}</code> format?'
            ' The <code>{pos}</code> should be an integer.'
        )
    return prepare_items(items, query, 'aminoacid mutation')


def prepare_items(items, query, value_type):
    for item in items:
        item['protein'] = item['protein'].to_json()
        item['mutation'] = item['mutation'].to_json()
        item['input'] = query
        item['type'] = value_type
    return items


def autocomplete_mutation(query, limit=None):
    """Returns: (autocompletion_mutation_results, are_there_more)"""
    # TODO: rewriting this into regexp-based set of function may increase readability
    # TODO: use limit to restrict queries

    query = query.upper().strip()
    data = query.split()

    items = []
    messages = []

    if len(data) == 1:

        if query.startswith('CHR'):
            messages += json_message('Awaiting for mutation in <code>{chrom} {pos} {ref} {alt}</code> format')

        gene = data[0].strip()

        if gene_exists(gene):
            messages += json_message('Awaiting for <code>{ref}{pos}{alt}</code> - expecting mutation in <code>{gene} {ref}{pos}{alt}</code> format')
        else:
            # return json_message('Gene %s not found in the database' % gene)
            pass

    elif len(data) == 4:
        chrom, pos, ref, alt = data

        if not query.startswith('CHR'):
            return []

        chrom = chrom[3:]

        try:
            items = bdb.get_genomic_muts(chrom, pos, ref, alt)

            # maybe an interesting mutation is located on the other strand
            if not items:
                query = 'complement of ' + query
                items = bdb.get_genomic_muts(chrom, pos, complement(ref), complement(alt))

            items = prepare_items(items, query, 'nucleotide mutation')
        except ValueError:
            return json_message(
                'Did you mean to search for mutation with <code>{chrom} {pos} {ref} {alt}</code> format?'
                ' The <code>{pos}</code> should be an integer.'
            )

    elif len(data) == 3:
        if not query.startswith('CHR'):
            return []

        return json_message('Awaiting for mutation in <code>{chrom} {pos} {ref} {alt}</code> format')

    elif len(data) == 2:
        gene, mut = data

        result = match_aa_mutation(gene, mut, query)
        items = [r for r in result if r['type'] != 'message']
        messages = [r for r in result if r['type'] == 'message']

        if query.startswith('CHR') and mut.isnumeric():
            messages += json_message('Awaiting for mutation in <code>{chrom} {pos} {ref} {alt}</code> format')

    if not limit:
        limit = len(items)
    return items[:limit] + messages, len(items) > limit
