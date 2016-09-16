var Filters = (function ()
{

    var box
    var form

    function update(e)
    {
        form.submit()
    }

    function checkEquality(obj1, obj2)
    {
        if(obj1.length != obj2.length)
            return false

        for(var i = 0; i < obj1.length; i++)
        {
            if(obj1[i] != obj2[i])
                return false
        }
        return true
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
                onDropdownShow: function(event)
                {
                    var target = $(event.target)

                    var selected = target.find('li.active')

                    target.data('prevoiously_selected', selected)
                },
                onDropdownHide: function(event)
                {
                    var target = $(event.target)

                    // selected counts also 'Select all' option
                    var selected = target.find('li.active')

                    // if there was not a change do not consider this action
                    if(checkEquality(selected, target.data('prevoiously_selected')))
                    {
                        return true
                    }
                    if (selected.length < 1)
                    {
                        target.parent().popover({
                            content: 'You should select at least one option',
                            placement: 'top',
                            trigger: 'manual'
                        }).popover('show')
                        return false
                    }
                    else {
                        target.parent().popover('hide')
                        update()
                    }

                },
                onChange: function(option, checked)
                {
                    if(checked)
                        $(option).parent().parent().popover('hide')
                },
                includeSelectAllOption: true,
                dropRight: true
            })
		}
	}

	return publicSpace
}())


Filters.init($('.filters')[0])
