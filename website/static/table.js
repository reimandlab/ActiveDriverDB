// require('kinase_tooltips.js')


var MutationTable = function ()
{
    var element
    var mutations
    var impact_importances = {}
    var mutation_template

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

    function initializeTooltips()
    {
        initializeKinaseTooltips()
    }

    function showMutation(mutation_id)
    {
        var data = element.bootstrapTable('getData', false);
        var index = null;
        for(var i = 0; i < data.length; i++)
        {
            if (data[i]._id === mutation_id)
            {
                index = i;
                break;
            }
        }
        if(index !== null)
        {
            var options = element.bootstrapTable('getOptions');
            var page = Math.floor(index / options.pageSize) + 1;
            element.bootstrapTable('selectPage', page);
            var row = getMutationRow(mutation_id);

            if(row)
            {
                publicSpace.expandRow(mutation_id);
                $('html, body').animate({
                    scrollTop: row.offset().top
                }, 2500);
            }
        }
    }

    var publicSpace = {
        init: function(table_element, mutations_list, impacts, mutation_url)
        {
            mutation_template = decodeURIComponent(mutation_url)

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
                var mutation_id = window.location.hash.substring(1);
                showMutation(mutation_id)
            }
            initializeTooltips()

            for(var j = 0; j < impacts.length; j++)
            {
                impact_importances[impacts[j]] = j
            }

        },
        expandRow: function(mutation_id)
        {
            var expanded_row = element.bootstrapTable(
                'expandRow',
                getMutationRow(mutation_id).data('index')
            )
            initializeKinaseTooltips(d3.select(expanded_row.get(0)).selectAll('.kinase'))
        },
        showMutation: showMutation,
        impactFormatter: function(value, row, index)
        {
            var mutation = mutations[row.pos + row.alt]
            return '<div class="' + mutation.category + ' badge">' + value + '</div>'
        },
        impactSorter: function (a, b)
        {
            // take only the first part of impact value (category, without MIMP change direction)
            a = a.split(' ')[0]
            b = b.split(' ')[0]
            if(impact_importances[a] < impact_importances[b]) return 1
            if(impact_importances[a] > impact_importances[b]) return -1
        },
        dbSNPFormatter: function(value, row, index)
        {
            var ids = mutations[row.pos + row.alt].meta['ClinVar']['dbSNP id'];
            var results = []
            for(var i = 0; i < ids.length; i++)
            {
                var id = ids[i]
                results.push('<a href="https://www.ncbi.nlm.nih.gov/snp/rs' + id + '" target="_blank">rs' + id + '</a>')
            }

            return results.join(', ')
        },
        mutationURLFormatter: function(value, row, index)
        {
            return '<a href="' + format(mutation_template, row) + '">' + value + '</a>'
        }
    }

    return publicSpace
}
