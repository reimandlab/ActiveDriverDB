var Filters = (function ()
{

    var box
    var form

    function update(e)
    {
        form.submit()
    }

	var publicSpace = {
		init: function(filter_box)
		{
            var box = $(filter_box)

            box.find('.save').hide()

            form = box.closest('form')

            var filters = box.find('.filter')
            for(var j = 0; j < filters.length; j++)
            {
                var filter = filters[j]
                var select = $(filter).find('select').not('.multiselect')
                select.change(update)
            }

            // initialize multiselect fields
            $('.multiselect').multiselect({
                onDropdownHidden: update,
                includeSelectAllOption: true,
                dropRight: true
            })
		}
	}

	return publicSpace
}())


Filters.init($('.filters')[0])
