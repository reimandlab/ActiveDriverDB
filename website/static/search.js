var SearchBar = (function ()
{

    target = ''

	function format(item, escape)
	{
		// var img = '<img src="/static/icons/"' + (item.img ? item.img : item.type) + '">'

		var html = '<div>' +
		'<span class="name">' + escape(item.value) + '</span>' +
		(item.owner && item.type != 'user' ? ('<span class="owner">' + escape(item.owner) + '</span>') : '') +
		// img +
		'</div>'

		return html
	}
	function onValueChange(value)
	{
        window.location = '/' + target + '/show/' + value
	}

	var publicSpace = {
		init: function(data)
		{
            elements = data.element

            target = data.target

			// always clear on load - prevent firefox from messing up
			elements.val('')

			elements.selectize({
				maxItems: 1,
				create: false,
				onChange: onValueChange,
				closeAfterSelect: true,
				valueField: 'value',
				labelField: 'value',
				optgroupField: 'type',
				optgroupValueField: 'id',
				optgroupLabelField: 'name',
				searchField: 'value',
				optgroups: [
					{id: 'protein', name: 'Protein'}
				],
				render: {
					option: format
				},
				load: function(query, callback) {
					if (!query.length)
					{
						return callback()
					}
					$.ajax({
						url: '/search/autocomplete/' + data.target,
						type: 'GET',
						data:
							{
								q: encodeURIComponent(query)
							},
						error: function() {
							callback()
						},
						success: function(rawRsult) {
							var result = JSON.parse(rawRsult)
							callback(result)
						}
					})
				}

			})
		}
	}

	return publicSpace
})()
