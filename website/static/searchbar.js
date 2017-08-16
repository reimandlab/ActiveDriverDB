var more_icon = '<span class="glyphicon glyphicon-chevron-right more"></span>';

var SearchBar = function ()
{
    var input
    var results_div
    var current_query
    var indicator
    var initial_results_content

    function default_template_result(result)
    {
        return '<a href="' + result.url + '" class="list-group-item">' + result.name + '</a>'
    }

    var config = {
        autocomplete_url: '/search/autocomplete_all',
        template: default_template_result
    }

    function update_results(raw_result, original_query) {

        // if we've got a result of an old query, it's not interesting anymore
        if(original_query !== current_query)
            return false

        var results = JSON.parse(raw_result)

        if(!results.entries.length)
        {
            results_div.html(config.template({
                name: 'No results found',
                type: 'message'
            }))
        }
        else
        {
            var html = ''
            for(var i = 0; i < results.entries.length; i++)
            {
                html += config.template(results.entries[i])
            }
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
                // arrow up
                if(e.which === 38)
                {
                    if(i > 0)
                        $(elements[i - 1]).focus()
                    else
                        input.focus()

                    return false
                }
                // arrow down
                else if(e.which === 40 && i + 1 < elements.length)
                {
                    $(elements[i + 1]).focus()
                    return false
                }
            })
        }
    }

    function search_on_type()
    {
        var query = input.val()

        // if the query has not changed, skip it
        if(current_query === query)
            return

        current_query = query

        // if the query is empty, clear up results
        if(!query)
        {
            results_div.html(initial_results_content)
            indicator.hide()
            return
        }

        $.ajax({
            url: config.autocomplete_url,
            type: 'GET',
            data: {q: encodeURIComponent(query)},
            success: function(query)
            {
                return function(result)
                {
                    return update_results(result, query)
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
            initial_results_content = results_div.html()

            input.on('change mouseup drop input', search_on_type)
            input.on('click', function(){ return false })
            input.on('focus', function(){ results_div.show() })
            input.on('keydown', function(e){
                // arrow down
                if(e.which === 40)
                {
                    results_div.find('.list-group-item').first().focus()
                    return false
                }
                if(e.which === 13)
                {
                    // pressing enter is equivalent to clicking on a first result,
                    // as requested in #124
                    results_div.find('.list-group-item').first().get(0).click()
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

    var cancer_template = 'Did you mean somatic cancer mutations of {{ name }} ({{ code }}) from TCGA?'
    var disease_template = 'Did you mean {{ name }} mutations from ClinVar?'
    var disease_in_protein_template = '{{ name }} mutations in {{ gene }} ({{ refseq }})'

    return (
        function (result)
        {
            var link, name = ''

            if('url' in result)
                link = '<a href="' + result.url + '" class="list-group-item">'

            switch(result.type)
            {
                case 'gene':
                    link = '<a href="/protein/show/' + result.preferred_isoform + '" class="list-group-item">'

                    if(result.isoforms_count > 1)
                        link += badge(result.isoforms_count + ' isoforms')

                    return link + result.name + '</a>'

                case 'aminoacid mutation':
                    name = result.mutation.name + ' (' + result.protein.refseq + ')';
                    return template_mutation(result, name)

                case 'nucleotide mutation':
                    name = result.mutation.name + ' (' + result.protein.refseq + ')' + ', result of ' + result.input
                    return template_mutation(result, name)

                case 'message':
                    return '<button type="button" class="list-group-item">' + result.name + '</button>'

                case 'pathway':
                    if(result.gene_ontology)
                        link += badge('Gene Ontology pathway')
                    if(result.reactome)
                        link += badge('Reactome pathway')

                    return link + result.name + '</a>'

                case 'cancer':
                    return link + format(cancer_template, result) + badge('Cancer') + '</a>'

                case 'disease':
                    return link + format(disease_template, result) + badge('Disease') + '</a>'

                case 'disease_in_protein':
                    return link + format(disease_in_protein_template, result) + badge('Disease mutations') + '</a>'

                case 'see_more':
                    return link + result.name + more_icon + '</a>'

            }
        }
    )
}
