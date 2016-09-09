var MutationTable = function ()
{
    var element

    function detailFormatter(index, row_data, element)
    {
        var impact = row_data[4]
        var affected_sites_count = row_data[5]
        html = 'Impact: ' + impact + '<br>'
        html += '# of affected sites: ' + affected_sites_count + '<br>'
        if(impact.indexOf('network-rewiring') !== -1)
        {
            var row_element = getMutationRow(row_data[0] + row_data[2])
            var meta = JSON.parse($(row_element).data('metadata').slice(2, -2).replace(/'/g, '"'))
            html += 'Affected site (based on MIMP): '
            for(var index in meta.MIMP.sites)
            {
                var site = meta.MIMP.sites[index]
                html += '<div>'
                html += 'Residue: ' + site.residue + '<br>'
                html += 'Position: ' + site.position + '<br>'
                html += 'Type: ' + site.type + '<br>'
                html += '</div>'
            }
            html += MIMP_image_from_meta(meta.MIMP)
        }
        else if(affected_sites_count != 0)
        {
            html += 'Closest affected site(s): <div>' + row_data[6] + '</div>'
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
