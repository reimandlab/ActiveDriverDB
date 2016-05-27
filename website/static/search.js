var SearchBar = (function ()
{

    target = ''

	function format(item, escape)
	{
		return '<div><span class="name">' + escape(item.value) + '</span></div>'
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
						success: function(rawResult) {
							var result = JSON.parse(rawResult)
							callback(result)
						}
					})
				}

			})
		}
	}

	return publicSpace
})()
