var SearchBar = (function ()
{
    var input
    var results_div
    var current_query

    var get_more = '<button type="submit" class="list-group-item">Get more results <span class="glyphicon glyphicon-chevron-right" aria-hidden="true"></span></button>'

    function templateResult(result)
    {
        var link = '<a href="/protein/show/' + result.preferred_isoform + '" class="list-group-item">'

        if(result.isoforms_count > 1)
            link += '<span class="badge">' + result.isoforms_count + ' isoforms</span>'

        link += result.name + '</a>'

        return link
    }

    function updateResults(rawResult, originalQuery) {

        // if we've got a result of an old query, it's not interesting anymore
        if(originalQuery != current_query)
            return false

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
        indicator.hide()
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

        if(!query || current_query == query)
            return

        current_query = query

        $.ajax({
            url: '/search/autocomplete_searchbar',
            type: 'GET',
            data: {q: encodeURIComponent(query)},
            success: function(query)
            {
                return function(result)
                {
                    return updateResults(result, query)
                }
            }(query)
        })

        indicator.show()
    }


    var publicSpace = {
        init: function(data)
        {
            input = $(data.input)
            results_div = $(data.results_div)
            indicator = $(data.indicator)

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

            $(document.body).on('click', function(){
                results_div.hide()
                indicator.hide()
            })
        }
    }

    return publicSpace
}())

SearchBar.init({
    'input': document.getElementById('search-bar'),
    'results_div': document.getElementById('search-quick-results'),
    'indicator': document.getElementById('waiting-indicator'),
})
