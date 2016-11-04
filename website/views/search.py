import json
from flask import render_template as template
from flask import request
from flask_classful import FlaskView
from flask_classful import route
from Levenshtein import distance
from models import Protein
from models import Gene
from website.views._commons import get_genomic_muts
from website.views._commons import get_protein_muts


class GeneResult:

    def __init__(self, gene, restrict_to_isoform=None):
        self.gene = gene
        if restrict_to_isoform:
            self.preffered_isoform = restrict_to_isoform

    def __getattr__(self, key):
        return getattr(self.gene, key)


def search_proteins(phase, limit=False):
    """Search for a protein isoform or gene.

    Limit means maximum results to be
    returned and will be applied to genes (so in the results there may be 10
    genes and 100 isoforms if the limit is equal to 10.
    """
    if not phase:
        return []

    # find by gene name
    name_filter = Gene.name.like(phase + '%')
    orm_query = Gene.query.filter(name_filter)
    if limit:
        orm_query = orm_query.limit(limit)
    genes = {gene.name: GeneResult(gene) for gene in orm_query.all()}

    # looking up both by name and refseq is costly - perform it wisely
    if phase.isnumeric():
        phase = 'NM_' + phase
    if phase.startswith('NM_'):
        refseq_filter = Protein.refseq.like(phase + '%')
        isoforms = Protein.query.filter(refseq_filter).all()

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


def parse_vcf(vcf_file, results, without_mutations, badly_formatted):

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

        if chrom.isnumeric():
            chrom = 'chr' + chrom

        alts = alts.split(',')
        for alt in alts:
            query += ' '.join((chrom, pos, ref, alt)) + '\n'
            items = get_genomic_muts(chrom, pos, ref, alt)
            if items:
                if len(alts) > 1:
                    line += ' (' + alt + ')'
                results.append(
                    {
                        'user_input': line,
                        'results': items
                    }
                )
            else:
                without_mutations.append(line)
    return query


def parse_text(textarea_query, results, without_mutations, badly_formatted):
    for line in textarea_query.split('\n'):
        data = line.split()
        if len(data) == 4:
            chrom, pos, ref, alt = [x.lower() for x in data]
            chrom = chrom[3:]

            items = get_genomic_muts(chrom, pos, ref, alt)

        elif len(data) == 2:
            gene, mut = [x.upper() for x in data]

            items = get_protein_muts(gene, mut)
        else:
            badly_formatted.append(line)
            continue

        if items:
            results.append(
                {
                    'user_input': line, 'results': items
                }
            )
        else:
            without_mutations.append(line)


def search_mutations(vcf_file, textarea_query):
    # note: entries from both file and textarea will be merged

    query = ''

    results = []
    without_mutations = []

    badly_formatted = []

    if vcf_file:
        query += parse_vcf(
            vcf_file, results, without_mutations, badly_formatted
        )

    if textarea_query:
        query += textarea_query
        parse_text(
            textarea_query, results, without_mutations, badly_formatted
        )

    return results, without_mutations, badly_formatted, query


class SearchView(FlaskView):
    """Enables searching in any of registered database models"""

    @route('/')
    def default(self):
        """Render default search form prompting to search for a protein"""
        return self.index(target='proteins')

    @route('/<target>', methods=['POST', 'GET'])
    def index(self, target):
        """Render search form and results (if any) for proteins or mutations"""

        without_mutations = []
        badly_formatted = []

        if target == 'proteins':
            # handle GET here
            assert request.method == 'GET'

            query = request.args.get(target) or ''

            results = search_proteins(query, 20)

        # if the target is 'mutations' but we did not received 'POST'
        elif target == 'mutations' and request.method == 'POST':

            textarea_query = request.form.get(target, False)
            vcf_file = request.files.get('vcf-file', False)

            results, without_mutations, badly_formatted, query = search_mutations(
                vcf_file, textarea_query
            )

            # TODO: redirect with an url containing session id, so user can
            # save line as a bookmark and return there later. We can create a
            # hash on the input - md5 should be enough.
            # redirect()
        else:
            query = ''
            results = []

        return template(
            'search/index.html',
            target=target,
            results=results,
            without_mutations=without_mutations,
            query=query,
            badly_formatted=badly_formatted
        )

    def form(self, target):
        """Return an empty HTML form appropriate for given target"""
        return template('search/form.html', target=target)

    def autocomplete_proteins(self, limit=20):
        """Autocompletion API for search for proteins"""
        # TODO: implement on client side requests with limit higher limits
        # and return the information about available results (.count()?)
        query = request.args.get('q') or ''

        entries = search_proteins(query, limit)

        response = [
            {
                'value': entry.name,
                'html': template('search/gene_results.html', gene=entry)
            }
            for entry in entries
        ]

        return json.dumps(response)

    def autocomplete_searchbar(self, limit=6):
        """Autocompletion API for search for proteins (untemplated)"""
        query = request.args.get('q') or ''

        entries = search_proteins(query, limit)

        response = [
            {
                'name': gene.name,
                'refseq': gene.preferred_isoform.refseq,
                'count': len(gene.isoforms)
            }
            for gene in entries
        ]

        return json.dumps(response)
