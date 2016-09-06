var MutationTable = function ()
{
    var element

    function detailFormatter(index, row, element)
    {
        var row_element = $('#' + row[0] + row[2])
        var meta = $(row_element).data('metadata')
        console.log(meta)
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
            html += 'MIMP'
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
