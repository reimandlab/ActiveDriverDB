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
    var element
    var empty_indicator, no_results_indicator, waiting_indicator
    var result_ul, recent_value, url_base, protein_search
    var search_endpoint = '/search/autocomplete_proteins'
    var filters_handler

    function get_url()
    {
        // TODO
        var href = url_base + 'proteins'

        return href
    }


    var load_data = function(data)
    {
        var results = data.results

        if(!results)
            return

        // TODO add an animation

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

    /**
     * Show "loading" or "no results found"
     */
    var on_loading_start = function()
    {
        var query = protein_search.val()
        result_ul.innerHTML = ''

        if(query)
        {
            no_results_indicator.addClass('hidden')
            if(query.length >= 1)
            {
                empty_indicator.addClass('hidden')
                waiting_indicator.removeClass('hidden')
            }
            else
            {
                empty_indicator.removeClass('hidden')
                waiting_indicator.addClass('hidden')
            }
        }
    }

    function setEventsForResults(result_box)
    {
        result_box.on('click', '.show-alt', function(event)
        {
            $(this).siblings('.alt-isoforms').toggleClass('js-hidden')
            $(this).toggleClass('js-shown')
            return false
        })

        // "alt-isoforms" have also "js-hidden" class
        // (so they will be hidden by default if js is enabled)
        // similarly with "show-alt" (but reverse)
    }

    var publicSpace = {
        /**
         *
         * @param dom_element - Form
         * @param _url_base
         */
        init: function(dom_element, _url_base)
        {
            Widgets.init(dom_element, function(){})

            element = $(dom_element)

            protein_search = element.find('input[name="filter[Search.query]"]')
            var result_box = $(element.find('.results')[0])
            result_ul = result_box.find('ul')[0]
            result_box.removeClass('hidden')
            empty_indicator = result_box.find('.empty')
            no_results_indicator = result_box.find('.no-results')
            waiting_indicator = result_box.find('.waiting')
            setEventsForResults(result_box)
            // TODO input cannot accept ":"

            recent_value = protein_search.val()

            var ready = function(){
                waiting_indicator.addClass('hidden')
                Widgets.init($('#filters_form'), function(){});
            }

            ready()

            filters_handler = AsyncFiltersHandler();

            filters_handler.init({
                form: dom_element,
                data_handler: load_data,
                endpoint_url: search_endpoint,
                on_loading_start: on_loading_start,
                on_loading_end: ready
            })

            var state_handlers = {
                filters: filters_handler
            };

            // handle change in history
            $(window).on('popstate', function(event) {
                var state = event.originalEvent.state;
                if(state)
                {
                    var handler = state_handlers[state.handler];
                    handler.apply(state.filters_query, true, true)
                }
            });

        },
        show: function() { element.show() },
        hide: function() { element.hide() },
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
        var activator = switches.filter('.' + target)    // because switch is reserved word
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
