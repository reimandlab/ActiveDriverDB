var SearchBar = function ()
{
    var input
    var results_div
    var current_query
    var indicator

    var get_more = '<button class="list-group-item">Get more results <span class="glyphicon glyphicon-chevron-right"></span></button>'

    function templateResult(result)
    {
        var link = '<a href="/protein/show/' + result.preferred_isoform + '" class="list-group-item">'

        if(result.isoforms_count > 1)
            link += '<span class="badge">' + result.isoforms_count + ' isoforms</span>'

        link += result.name + '</a>'

        return link
    }

    var config = {
        autocomplete_url: '/search/autocomplete_all',
        template: templateResult
    }

    function updateResults(rawResult, originalQuery) {

        // if we've got a result of an old query, it's not interesting anymore
        if(originalQuery != current_query)
            return false

        var results = JSON.parse(rawResult)

        if(!results.entries.length)
        {
            results_div.html(templateResult({
                name: 'No results found'
            }))
        }
        else
        {
            var html = ''
            var length = Math.min(results.entries.length, 5)
            for(var i = 0; i < length; i++)
            {
                html += config.template(results.entries[i], results)
            }
            if(results.entries.length > 5)
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
            url: config.autocomplete_url,
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
            update_object(config, data)
            var box = $(data.box)
            input = box.find('input')
            results_div = box.find('.bar-results')
            indicator = box.find('.waiting-indicator')

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
}


function badge(name) {
    return '<span class="badge">' + name + '</span>';
}

function advanced_searchbar_templator(mutation_template)
{

    function template_mutation(result, name)
    {
        var badges = '';

        if(result.mutation.is_confirmed)
            badges += badge('known mutation');

        if(result.mutation.is_ptm)
            badges += badge('PTM mutation');

        if(result.protein.is_preferred)
            badges += badge('preferred isoform');

        return format(mutation_template, {
            name: name,
            refseq: result.protein.refseq,
            pos: result.pos,
            alt: result.alt,
            badges: badges
        });

    }

    return (
        function (result, results)
        {
            var type = results.type

            if(type === 'gene'){
                var link = '<a href="/protein/show/' + result.preferred_isoform + '" class="list-group-item">'

                if(result.isoforms_count > 1)
                    link += '<span class="badge">' + result.isoforms_count + ' isoforms</span>'

                link += result.name + '</a>'

                return link
            }
            else if(type === 'aminoacid mutation'){
                var name = result.mutation.name + ' (' + result.protein.refseq + ')';
                return template_mutation(result, name)
            }
            else if(type === 'nucleotide mutation'){
                var name = result.mutation.name + ' (' + result.protein.refseq + ')' + ', result of ' + result.input
                return template_mutation(result, name)
            }
            else if(type === 'message')
            {
                return '<button class="list-group-item">' + result.name + '</button>'
            }

        }
    )
}
