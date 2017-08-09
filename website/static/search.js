// TODO: Inheritance from form to implement Form interface (show/hide/etc)
// That's very hard to do cross-browser in pure JS

var multilinePlaceholderPolyfill = (function()
{
    // allows to use multiline placeholders if textarea is given as field,
    // or imitates normal placeholders if an input is given as field
    var field

    // is placeholder content displayed inside the field?
    // (double state control allows user to type in a text identical to placeholder)
    var active

    var placeholder = ''

    function startPlaceholder()
    {
        if(!active && !field.val())
        {
            field.val(placeholder)
            field.addClass('placeholder')
            active = true
        }
    }

    function stopPlaceholder()
    {
        if(active && field.val() === placeholder)
        {
            field.val('')
            field.removeClass('placeholder')
            active = false
        }
    }

    var publicSpace = {
        init: function(element, initial_placeholder)
        {
            field = $(element)

            placeholder = initial_placeholder.replace(/\\n/g, '\n')
            var multiline = placeholder.indexOf('\n') > -1

            // only Chrome supports multiline placeholders.
            if('placeholder' in element[0] && (window.chrome || !multiline))
            {
                field.attr('placeholder', placeholder)
            }
            else
            {
                field.attr('placeholder', '')

                startPlaceholder()

                field.on('blur', startPlaceholder)
                field.on('focus', stopPlaceholder)
                field.closest('form').on('submit', stopPlaceholder)
            }
        },
        setValue: function(value)
        {
            stopPlaceholder()
            field.val(value)
        }
    }

    return publicSpace
})

var ProteinForm = (function ()
{
    var element, search_button
    var empty_indicator, no_results_indicator, waiting_indicator
    var result_ul, recent_value, url_base

    function get_url()
    {
        var href = url_base + 'proteins'
        var params = get_url_params()
        if(recent_value !== undefined && recent_value !== '')
        {
            params.proteins = recent_value
        }
        else
        {
            delete params.proteins
        }

        var query_string = $.param(params)
        if(query_string)
        {
            href += '?' + query_string
        }
        return href
    }

    function autocomplete(query)
    {
        var params = get_url_params()
        params.q = encodeURIComponent(query)
        result_ul.innerHTML = ''
        $.ajax({
            url: '/search/autocomplete_proteins',
            type: 'GET',
            data: params,
            success: function(response) {

                // do we still need this?
                if(response.query !== recent_value)
                    return

                var results = response.results
                // TODO add animation

                waiting_indicator.addClass('hidden')
                if(!results.length)
                {
                    no_results_indicator.removeClass('hidden')
                }
                else
                {
                    no_results_indicator.addClass('hidden')
                    for(var i = 0; i < results.length; i++)
                    {
                        result_ul.innerHTML += results[i].html
                    }
                }

            }
        })
    }

    function onChangeHandler(event)
    {
        var query = $(event.target).val()

        if(query === recent_value)
            return

        if(query)
        {
            no_results_indicator.addClass('hidden')
            if(query.length >= 3)
            {
                empty_indicator.addClass('hidden')
                waiting_indicator.removeClass('hidden')
                search_button.hide()
                autocomplete(query)
            }
            else
            {
                search_button.show()
                result_ul.innerHTML = ''
                empty_indicator.removeClass('hidden')
                waiting_indicator.addClass('hidden')
            }
        }

        recent_value = query

        history.replaceState(history.state, null, get_url())

    }

    function ToggleAlternativeIsoforms()
    {
        $('.alt-isoforms').toggleClass('hidden', true)
        $('.show-alt').toggleClass('hidden', false)
    }

    function setEventsForResults(result_box)
    {
        $(result_box).on('click', '.show-alt', function(event)
        {
            $(this).siblings('.alt-isoforms').toggleClass('js-hidden')
            $(this).toggleClass('js-shown')
        })

        // "alt-isoforms" have also "js-hidden" class
        // (so they will be hidden by default if js is enabled)
        // similarly with "show-alt" (but reverse)

    }

    var publicSpace = {
        init: function(dom_element, _url_base)
        {
            element = dom_element
            url_base = _url_base
            search_button = $(element).find('button[type="submit"].search-button')
            var protein_search = $(element).find('#protein_search')
            // handle all edge cases like dragging the text into the input
            protein_search.on('change mouseup drop input', onChangeHandler)
            var result_box = $(element).find('.results')[0]
            result_ul = $(result_box).find('ul')[0]
            $(result_box).removeClass('hidden')
            empty_indicator = $(result_box).find('.empty')
            no_results_indicator = $(result_box).find('.no-results')
            waiting_indicator = $(result_box).find('.waiting')

            var placeholder_manager = multilinePlaceholderPolyfill()
            placeholder_manager.init(
                protein_search,
                protein_search.attr('placeholder')
            )

            setEventsForResults(result_box)


        },
        show: function()
        {
            $(element).show()
            // TODO show/hide animations
        },
        hide: function()
        {
            $(element).hide()
        },
        get_url: get_url
    }
    return publicSpace
}())

var MutationForm = (function ()
{
    var element,
        textarea,
        placeholder_manager,
        url_base

    function getPlaceholder()
    {
        return textarea.attr('data-full-placeholder')
    }

    function setExample()
    {
        var value = this.href
        value = decodeURIComponent(value.substr(value.lastIndexOf('=') + 1))
        placeholder_manager.setValue(value)

        // prevent default
        return false
    }

    var publicSpace = {
        init: function(dom_element, _url_base)
        {
            element = dom_element
            url_base = _url_base
            textarea = element.find('.muts-textarea')

            placeholder_manager = multilinePlaceholderPolyfill()
            placeholder_manager.init(textarea, getPlaceholder())

            element.find('.set-example').on('click', setExample)

        },
        show: function()
        {
            $(element).show()
        },
        hide: function()
        {
            $(element).hide()
        },
        get_url: function()
        {
            return url_base + 'mutations'
        }
    }

    return publicSpace
}())


var SearchManager = (function ()
{
    var target = '',
        url_base,
        form_area,
        switches,
        forms = [],
        form_constructor = {
            proteins: ProteinForm,
            mutations: MutationForm
        }

    function get_form(name)
    {
        $.ajax({
            url: '/search/form/' + name,
            type: 'GET',
            async: false,
            success: function(code)
            {
                add_form(code)
                initialize_form(name)
            }
        })
    }

    function add_form(html_code)
    {
        $(form_area).after(html_code)
    }

    function initialize_form(name)
    {
        var selector = '#' + name + '-form'
        var dom_form = $(selector)
        if(!dom_form.length)
        {
            return
        }
        forms[name] = form_constructor[name]
        forms[name].init(dom_form, url_base)
    }

    function switchFromAnchor()
    {
        // get new target
        var href = this.href
        target = href.substr(href.lastIndexOf('/') + 1)

        switchTarget(target)

        // prevent default
        return false
    }

    function switchTarget(new_target, silent)
    {
        var old_target = target
        target = new_target

        // update switches
        var activator =    switches.filter('.' + target)    // because switch is reserved word
        switches.not(activator).removeClass('active')
        $(activator).addClass('active')

        // fetch form if not loaded
        if(!(target in forms))
        {
            get_form(target)
        }

        // switch forms
        for(var key in forms)
        {
            if(forms.hasOwnProperty(key) && key !== target)
            {
                forms[key].hide()
            }
        }
        forms[target].show()

        // save the new address
        if(!silent)
        {
            history.pushState({target: old_target}, null, forms[target].get_url())
        }
    }

    var publicSpace = {
        init: function(data)
        {
            form_area = data.form_area
            target = data.active_target
            url_base = decodeURIComponent(data.url_base)
            switches = $('.target-switch a')

            switches.on('click', switchFromAnchor)
            initialize_form('proteins')
            initialize_form('mutations')

            // handle change in history
            $(window).on('popstate', function(event) {
                var state = event.originalEvent.state
                switchTarget(state.target, true)
            })

        }
    }

    return publicSpace
}())
