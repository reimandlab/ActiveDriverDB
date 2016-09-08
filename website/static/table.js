var MutationTable = function ()
{
    var element

    function detailFormatter(index, row, element)
    {
        var impact = row[4]
        var affected_sites_count = row[5]
        html = 'Impact: ' + impact + '<br>'
        html += '# of affected sites: ' + affected_sites_count + '<br>'
        if(affected_sites_count != 0)
        {
            html += 'Closest affected site(s): <div>' + row[6] + '</div>'
        }
        if(impact == 'network-rewiring')
        {
            var row_element = $('#' + row[0] + row[2])
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
                detailFormatter: detailFormatter
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
        }
    }

    return publicSpace
}
