// TODO: Inheritance from form to implement Form interface (show/hide/etc)
// That's very hard to do cross-browser in pure JS

var multlinePlaceholderPolyfill = (function()
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
        if(active && field.val() == placeholder)
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
    var empty_indicator
    var result_ul
    var recent_value

    function get_url()
    {
        var href = 'proteins'
        if(recent_value !== undefined && recent_value !== '')
        {
            href += '?proteins=' + recent_value
        }
        return href
    }

    // TODO autocomplete should only show quick sugesstion?
    // TODO and use search instead? Moot point.
    function autocomplete(query)
    {
        $.ajax({
            url: '/search/autocomplete_proteins',
            type: 'GET',
            data:
                {
                    q: encodeURIComponent(query)
                },
            success: function(rawResult) {
                var results = JSON.parse(rawResult)
                // TODO add animation
                result_ul.innerHTML = ''
                for(var i = 0; i < results.length; i++)
                {
                    result_ul.innerHTML += results[i].html
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
            if(!recent_value)
            {
                empty_indicator.addClass('hidden')
            }
            autocomplete(query)
        }
        else if(!query && recent_value)
        {
            result_ul.innerHTML = ''
            empty_indicator.removeClass('hidden')
        }

        recent_value = query

        history.replaceState(history.state, null, get_url())

    }

    function setEventsForResults(result_box)
    {
        $(result_box).on('click', '.show-alt', function(event)
        {
            $(this).siblings('.alt-isoforms').toggleClass('hidden')
            $(this).hide()
        })
        $('.alt-isoforms').toggleClass('hidden', true)
        $('.show-alt').toggleClass('hidden', false)
    }

    var publicSpace = {
        init: function(dom_element)
        {
            element = dom_element
            $(element).find('button[type="submit"]').hide()
            // handle all edge cases like dragging the text into the input
            var protein_search = $(element).find('#protein_search')
            protein_search.on('change mouseup drop input', onChangeHandler)
            var result_box = $(element).find('.results')[0]
            result_ul = $(result_box).find('ul')[0]
            $(result_box).removeClass('hidden')
            empty_indicator = $(result_box).find('.empty')

            var placeholder_manager = multlinePlaceholderPolyfill()
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
    var element
    var textarea
    var placeholder_manager

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
        init: function(dom_element)
        {
            element = dom_element
            textarea = element.find('textarea')

            placeholder_manager = multlinePlaceholderPolyfill()
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
            return 'mutations'
        }
    }

    return publicSpace
}())


var SearchManager = (function ()
{
    var target = ''
    var form_area
    var switches
    var forms = []
    var form_constructor = {
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
        forms[name].init(dom_form)
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

    function switchTarget(new_target, silient)
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
        if(!silient)
        {
            history.pushState({target: old_target}, null, forms[target].get_url())
        }
    }

    var publicSpace = {
        init: function(data)
        {
            form_area = data.form_area
            target = data.active_target
            switches = $('.target-switch a')

            switches.on('click', switchFromAnchor)
            initialize_form('proteins')
            initialize_form('mutations')

            var location = window.history.location || window.location

            $(window).on('popstate', function(event) {
                state = event.originalEvent.state
                switchTarget(state.target, true)
            })

        }
    }

    return publicSpace
}())
