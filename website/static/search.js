// TODO: Inheritance from form to implement Form interface (show/hide/etc)
// That's very hard to do cross-browser in pure JS

var ProteinForm = (function ()
{
	var element
	var result_box
	var recent_value

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
				result_box.innerHTML = ''
				for(var i = 0; i < results.length; i++)
				{
					result_box.innerHTML += results[i].html
				}
			}
		})
	}

	function onChangeHandler()
	{
		var query = $(event.target).val()
		if(query && query != recent_value)
		{
			recent_value = query
			autocomplete(query)
		}
	}

	var publicSpace = {
		init: function(dom_element)
		{
			element = dom_element
			$(element).find('button[type="submit"]').hide()
			// handle all edge cases like dragging the text into the input
			$(element).find('#protein_search').on('change mouseup drop input', onChangeHandler)
			result_box = $(element).find('.results')[0]
			$(result_box).removeClass('hidden')
		}, 
		show: function()
		{
			$(element).show()
			// TODO show/hide animations
		},
		hide: function()
		{
			$(element).hide()
		}
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
			history.pushState({target: old_target}, null, target)
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
