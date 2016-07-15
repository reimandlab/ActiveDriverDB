import json
from flask import render_template as template
from flask import request
from flask_classful import FlaskView
from flask_classful import route
from website.models import Protein
from website.models import Gene
from database import bdb
from database import make_snv_key
from database import decode_csv


class GeneResult:

    def __init__(self, gene, restrict_to=None):
        self.gene = gene
        if restrict_to:
            self.isoforms = restrict_to

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
                genes[gene.name] = GeneResult(gene, restrict_to=[isoform])

    return genes.values()


class SearchView(FlaskView):
    """Enables searching in any of registered database models"""

    @route('/')
    def default(self):
        """Render default search form prompting to search for a protein"""
        return self.index(target='proteins')

    @route('/<target>', methods=['POST', 'GET'])
    def index(self, target):
        """Render search form and results (if any) for proteins or mutations"""

        if target == 'proteins':
            # handle GET here
            assert request.method == 'GET'

            query = request.args.get(target) or ''

            results = search_proteins(query, 20)

        # if the target is 'mutations' but we did not received 'POST'
        elif target == 'mutations' and request.method == 'POST':

            query = ''

            textarea_query = request.form.get(target, False)
            vcf_file = request.files.get('vcf_file', False)

            # TODO: add a notice for user that if there is a file, the entries
            # from both file and textarea will be merged

            results = []

            if vcf_file:
                for line in vcf_file:
                    # TODO
                    results.append(line)
            if textarea_query:
                query += textarea_query
                for line in textarea_query.lower().split('\n'):
                    data = line.split()
                    if len(data) == 4:
                        chrom, pos, ref, alt = data
                        chrom = chrom[3:]
                        snv = make_snv_key(chrom, pos, ref, alt)
                        items = [
                            decode_csv(item)
                            for item in bdb[snv]
                        ]
                        for item in items:
                            item[-1] = Protein.query.get(item[-1])

                        results.append(
                            {
                                'chrom': chrom, 'pos': pos, 'ref': ref,
                                'alt': alt, 'results': items
                            }
                        )
                    elif len(data) == 2:
                        # TODO - protein handling
                        pass

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
            query=query,
        )

    def form(self, target):
        """Return an empty HTML form appropriate for given target"""
        return template('search/form.html', target=target)

    def autocomplete_proteins(self, limit=20):
        """Autocompletion API for search for target model (by name)"""
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
