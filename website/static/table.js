var MutationTable = function ()
{
    var element

    function detailFormatter(index, row_data, element)
    {
        var impact = row_data[4]
        var affected_sites_count = row_data[5]
        html = 'Impact: ' + impact + '<br>'
        html += '# of affected sites: ' + affected_sites_count + '<br>'
        if(affected_sites_count != 0)
        {
            html += 'Closest affected site(s): <div>' + row_data[6] + '</div>'
        }
        if(impact == 'network-rewiring')
        {
            var row_element = getMutationRow(row_data[0] + row_data[2])
            var meta = JSON.parse($(row_element).data('metadata').slice(2, -2).replace(/'/g, '"'))
            html += MIMP_image_from_meta(meta.MIMP)
        }
        return html
    }

    function getMutationRow(mutation_id)
    {
        return $('#' + mutation_id)
    }

    var publicSpace = {
        init: function(table_element)
        {
            element = table_element
            element.bootstrapTable({
                detailFormatter: detailFormatter,
                onClickRow: function(row_data){
                    publicSpace.expandRow(row_data[0] + row_data[2])
                },
            })
            if(window.location.hash)
            {
                publicSpace.expandRow(window.location.hash.substring(1))
            }
        },
        expandRow: function(mutation_id)
        {
            element.bootstrapTable(
                'expandRow',
                getMutationRow(mutation_id).data('index')
            )
        },
    }

    return publicSpace
}
