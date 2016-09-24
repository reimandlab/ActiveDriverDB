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
