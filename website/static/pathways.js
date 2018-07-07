
function initTable($table, query, additional_columns)
{
    var initial_query = query

    function detailFormatter(index, row, $element)
    {

        $element.html('Loading...');

        var url;
        if(row.reactome)
            url = format(reactome_url, row);
        else
            url = format(gene_ontology_url, row);

        $.get(url, function (details) {
            $element.html(
                nunjucks.render(
                    'pathway_details.njk',
                    {
                        pathway: details
                    }
                )
            )
        });

    }

    function pathway_formatter(value, row, index)
    {
        if(row.reactome)
            return '<a href="' + reactome_show.replace('0', row.reactome) + '">' + value + '</a>'
        if(row.gene_ontology)
            return '<a href="' + gene_ontology_show.replace('0', row.gene_ontology) + '">' + value + '</a>'
        return value
    }

    function idFormatter(value, row, index)
    {
        var ids = []
        if(row.reactome)
            ids.push(format(
                'Reactome: <a href="http://www.reactome.org/content/detail/R-HSA-{{ reactome }}">{{ reactome }}</a>',
                row
            ))
        if(row.gene_ontology)
            ids.push(format(
                'GO: <a href="http://amigo.geneontology.org/amigo/term/GO:{{ gene_ontology }}">{{ gene_ontology }}</a>',
                row
            ))
        return ids.join('\n')
    }

    function genesFormatter(value, row, index)
    {
        //nunjucks.installJinjaCompat()
        return nunjucks.render(
            'pathways_gene_list.njk',
            {
                genes: value,
                more: true
            }
        )
    }

    var columns = [
        {
            title: 'Name',
            field: 'description',
            align: 'center',
            valign: 'middle',
            sortable: true,
            formatter: pathway_formatter
        },
        {
            title: 'Pathway ID',
            align: 'center',
            width: '150px',
            valign: 'middle',
            formatter: idFormatter
        },
        {
            field: 'gene_ontology',
            title: 'Gene Ontology ID',
            sortable: true,
            visible: false,
            align: 'center'
        },
        {
            field: 'reactome',
            title: 'Reactome ID',
            sortable: true,
            visible: false,
            align: 'center'
        },
        {
            title: '# Genes',
            sortable: true,
            valign: 'middle',
            align: 'center',
            field: 'gene_count'
        },
        {
            title: 'Genes',
            //sortable: true,
            valign: 'middle',
            align: 'center',
            field: 'genes',
            formatter: genesFormatter
        }
    ]
    if(additional_columns)
        append(columns, additional_columns)

    $table.bootstrapTable({
        detailFormatter: detailFormatter,
        columns: columns,
        formatLoadingMessage: function ()
        {
            return 'Loading, please wait... <span class="glyphicon glyphicon-refresh glyphicon-spin"></span>'
        },
        onSearch: function () {
            $table.bootstrapTable('showLoading')
        },
        silentSort: false,
        queryParams: function(params){
            if(initial_query)
            {
                params['search'] = initial_query
                initial_query = null
            }
            return params
        }
    })

    $table.on('click-row.bs.table', function (e, row, $element)
    {
        $table.bootstrapTable(
            'expandRow',
            $element.data('index')
        );
    })

    setTimeout(function () {$('.bootstrap-table .search input').val(query)}, 0)
}

/** Used as callback for buttons on list */
function show_all_genes(btn)
{
    var btn = $(btn)
    btn.closest('.gene-list').find('li').css('display', 'inline');
    btn.hide();
    event.stopPropagation()
    return false
}

