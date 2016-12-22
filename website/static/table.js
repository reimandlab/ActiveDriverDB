var MutationTable = function ()
{
    var element
    var mutations

    function detailFormatter(index, row_data, element)
    {
        var mutation_id = row_data._id
        var mutation = mutations[mutation_id]

        return nunjucks.render(
            'row_details.njk',
            {mutation: mutation}
        )
    }

    function getMutationRow(mutation_id)
    {
        return $('#' + mutation_id)
    }

    function get_protein_details_url(refseq)
    {
        var href = '/protein/details/' + refseq
        var params = get_url_params()

        var query_string = $.param(params)
        if(query_string)
        {
            href += '?' + query_string
        }
        return href
    }

    function initializeTooltips()
    {
        var kinase_tooltip = Tooltip()
        kinase_tooltip.init({
            id: 'kinase',
            preprocess_data: function(d, render_template_cb){
                context = this
                $.ajax({
                  url: get_protein_details_url(
                      $(this).data('refseq')
                  ),
                  success: function(data){
                      render_template_cb.call(context, data)
                  }
                })
            },
            template: function(kinase){
                return nunjucks.render(
                    'kinase_tooltip.njk',
                    {
                        kinase: kinase,
                        site: $(this).data('site')
                    }
                )
            }
        })
        var kinases = d3.selectAll('.kinase')
            .call(kinase_tooltip.bind)
    }

    var publicSpace = {
        init: function(table_element, mutations_list)
        {
            mutations = {}
            for(var i = 0; i < mutations_list.length; i++)
            {
                var mutation = mutations_list[i]
                mutations[mutation.pos + mutation.alt] = mutation
            }
            element = table_element
            element.bootstrapTable({
                detailFormatter: detailFormatter,
                onClickRow: function(row_data){
                    publicSpace.expandRow(row_data._id)
                }
            })
            if(window.location.hash)
            {
                publicSpace.expandRow(window.location.hash.substring(1))
            }
            initializeTooltips()
        },
        expandRow: function(mutation_id)
        {
            element.bootstrapTable(
                'expandRow',
                getMutationRow(mutation_id).data('index')
            )
        }
    }

    return publicSpace
}
