// TODO: Inheritance from form to implement Form interface (show/hide/etc)
// That's very hard to do cross-browser in pure JS

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
			url: '/search/autocomplete/proteins',
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

		if(query == recent_value)
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

	var publicSpace = {
		init: function(dom_element)
		{
			element = dom_element
			$(element).find('button[type="submit"]').hide()
			// handle all edge cases like dragging the text into the input
			$(element).find('#protein_search').on('change mouseup drop input', onChangeHandler)
			var result_box = $(element).find('.results')[0]
			result_ul = $(result_box).find('ul')[0]
			$(result_box).removeClass('hidden')
			empty_indicator = $(result_box).find('.empty')
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

	function replacePlaceholder()
	{
		// there will be browser not supporting multiline placeholders despite the trick.
		// further tests are required - for those browsers we can display a bar with the text of full placeholder above
		textarea.attr('placeholder', textarea.attr('data-full-placeholder').replace(/\\n/g, '\n'))
	}

	var publicSpace = {
		init: function(dom_element)
		{
			element = dom_element
			textarea = element.find('textarea')
			replacePlaceholder()
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
		var activator =	switches.filter('.' + target)	// because switch is reserved word
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
			if(forms.hasOwnProperty(key) && key != target)
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
