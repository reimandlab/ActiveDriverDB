var SearchBar = (function ()
{
    var input
    var results_div
    var old_query

    var get_more = '<a href="/search/proteins" class="list-group-item">Get more results <span class="glyphicon glyphicon-chevron-right" aria-hidden="true"></span></a>'

    function templateResult(result)
    {
        var link = '<a href="/protein/show/' + result.refseq + '" class="list-group-item">'

        if(result.count > 1)
            link += '<span class="badge">' + result.count + ' isoforms</span>'

        link += result.name + '</a>'

        return link
    }

    function updateResults(rawResult) {
        var results = JSON.parse(rawResult)

        if(!results.length)
        {
            results_div.html(templateResult({
                name: 'No results found'
            }))
        }
        else
        {
            var html = ''
            var length = Math.min(results.length, 5)
            for(var i = 0; i < length; i++)
            {
                html += templateResult(results[i])
            }
            if(results.length > 5)
                html += get_more
            results_div.html(html)

        }

    }

    function searchOnType()
    {
        var query = input.val()

        if(!query || old_query == query)
            return

        old_query = query

        $.ajax({
            url: '/search/autocomplete_searchbar',
            type: 'GET',
            data: { q: encodeURIComponent(query) },
            success: updateResults
        })
    }


    var publicSpace = {
        init: function(data)
        {
            input = $(data.input)
            results_div = $(data.results_div)

            input.on('change mouseup drop input', searchOnType)
            input.on('click', function(){ return false })
            input.on('focus', function(){ results_div.show() })

            $(document.body).on('click', function(){ results_div.hide() })
        }
    }

    return publicSpace
}())

SearchBar.init({
    'input': document.getElementById('search-bar'),
    'results_div': document.getElementById('search-quick-results')
})
