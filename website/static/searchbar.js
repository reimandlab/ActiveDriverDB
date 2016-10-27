var SearchBar = (function ()
{
    var input
    var results_div
    var old_query

    var get_more = '<button type="submit" class="list-group-item">Get more results <span class="glyphicon glyphicon-chevron-right" aria-hidden="true"></span></button>'

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

            add_dropdown_navigation(results_div)

        }

    }

    function add_dropdown_navigation(dropdown_element)
    {
        var elements = dropdown_element.find('.list-group-item')
        for(var i = 0; i < elements.length; i++)
        {
            $(elements[i]).on('keydown', {i: i}, function(e)
            {
                var i = e.data.i
                if(e.key == 'ArrowUp')
                {
                    if(i > 0)
                        $(elements[i - 1]).focus()
                    else
                        input.focus()

                    return false
                }
                else if(e.key == 'ArrowDown' && i + 1 < elements.length)
                {
                    $(elements[i + 1]).focus()
                    return false
                }
            })
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
            input.on('keydown', function(e){
                if(e.key == 'ArrowDown')
                {
                    results_div.find('.list-group-item').first().focus()
                    return false
                }
            })

            add_dropdown_navigation(results_div)

            $(document.body).on('click', function(){ results_div.hide() })
        }
    }

    return publicSpace
}())

SearchBar.init({
    'input': document.getElementById('search-bar'),
    'results_div': document.getElementById('search-quick-results')
})
