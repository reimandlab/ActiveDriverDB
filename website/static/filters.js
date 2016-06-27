var Filters = (function ()
{

    function update(e)
    {
        this.closest('form').submit()
    }

	var publicSpace = {
		init: function(data)
		{
            var boxes = $('.filters')
            for(var i = 0; i < boxes.length; i++)
            {
                var box = $(boxes[i])

                box.find('.save').hide()

                var filters = box.find('.filter')
                for(var j = 0; j < filters.length; j++)
                {
                    var filter = filters[j]
                    var select = $(filter).find('select')
                    select.change(update)
                }

            }
		}
	}

	return publicSpace
}())


Filters.init()
