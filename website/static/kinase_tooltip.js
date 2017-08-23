// require('common.js')
// require('tooltip.js')


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

function initializeKinaseTooltips()
{
    var kinase_tooltip = Tooltip()
    kinase_tooltip.init({
        id: 'kinase',
        preprocess_data: function (d, render_template_cb) {
            var context = this
            $.ajax({
                url: get_protein_details_url(
                    $(this).data('refseq')
                ),
                success: function (data) {
                    render_template_cb.call(context, data)
                }
            })
        },
        template: function (kinase) {
            return nunjucks.render(
                'kinase_tooltip.njk',
                {
                    kinase: kinase,
                    site: $(this).data('site')
                }
            )
        }
    })
    d3.selectAll('.kinase')
        .call(kinase_tooltip.bind)
}