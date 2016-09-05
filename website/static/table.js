var MutationTable = function ()
{
    var element

    function detailFormatter(index, row, element)
    {
        html = 'Impact: ' + row[5] + '<br>'
        html += 'Sites affected: ' + row[6] + '<br>'
        html += 'Closest affected site(s): <div>' + row[7] + '</div>'
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
