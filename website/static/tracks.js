var Tracks = (function ()
{

    function scroll(tracks, direction)
    {
        var pos = tracks.scrollLeft()
        var len = tracks.width()
        tracks.animate({scrollLeft: pos + len * direction }, '300', 'swing')
    }

	function scrollLeft()
	{
        var tracks = $(this)
        scroll(tracks, -1)
	}


	function scrollRight()
	{
        var tracks = $(this)
        scroll(tracks, +1)
	}


    function initButtons(buttons, func, context)
    {
        for(var i = 0; i < buttons.length; i++)
        {
            var button = $(buttons[i])
            button.click($.proxy(func, context))
        }
    }

	var publicSpace = {
		init: function(data)
		{
            var boxes = $('.tracks-box')
            for(var i = 0; i < boxes.length; i++)
            {
                var box = $(boxes[i])
        
                var tracks = box.find('.tracks')

                var scrollArea = tracks.find('.scroll-area')

                var buttons = box.find('.scroll-left')
                initButtons(buttons, scrollLeft, scrollArea)

                var buttons = box.find('.scroll-right')
                initButtons(buttons, scrollRight, scrollArea)

                var controls = box.find('.controls')
                for(var j = 0; j < controls.length; j++)
                {
                    $(controls[i]).show()
                }
            }
		}
	}

	return publicSpace
})()


Tracks.init()
