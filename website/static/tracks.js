var Tracks = (function ()
{

    var minFontSize = 0.1
    var maxFontSize = 20

    function zoom(area, direction)
    {
        // possible refinements: max + css animations
        var size = parseFloat(area.css('font-size'))
        // scale down slower toward 0
        size += direction * size / 15

        size = Math.max(size, minFontSize)
        size = Math.min(size, maxFontSize)

        area.css('font-size', size + 'px')
    }

    function zoomIn()
    {
        var area = $(this)
        zoom(area, +1)
    }

    function zoomOut()
    {
        var area = $(this)
        zoom(area, -1)
    }

    function scroll(area, direction)
    {
        var pos = area.scrollLeft()
        var len = area.width()
        area.stop().animate({scrollLeft: pos + len * direction }, '300', 'swing')
    }

	function scrollLeft()
	{
        var area = $(this)
        scroll(area, -1)
	}


	function scrollRight()
	{
        var area = $(this)
        scroll(area, +1)
	}

    function getCharSize(sequence)
    {
        var elements = sequence.children('.elements')
        var seq = $.trim(elements.text())
        elements.wrapInner('<span></span>')
        var span = elements.children('span')
        var charSize = span.innerWidth() / seq.length
        span.contents().unwrap()
        return charSize
    }

	function scrollTo()
	{
        var input = $(this).closest('.input-group').find('.scroll-to-input')
        var tracks = $(this).closest('.tracks-box')
        var area = tracks.find('.scroll-area')
        var sequence = tracks.find('.sequence')
        // - 1: sequence is 1 based but position is 0 based
        var pos = $(input).val() - 1

        var charSize = getCharSize(sequence)
        area.animate({scrollLeft: pos * charSize }, '300', 'swing')
	}

    function initButtons(buttons, func, context)
    {
        for(var i = 0; i < buttons.length; i++)
        {
            var button = $(buttons[i])
            if(context)
            {
                button.click($.proxy(func, context))
            }
            else
            {
                button.click(func)
            }
        }
    }

    function initFields(fields, func)
    {
        for(var i = 0; i < fields.length; i++)
        {
            $(fields[i]).keyup(function(e)
            {
                if(e.keyCode == 13)
                {
                    func.call(this)
                }
            })
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
                
                var innerDiv = box.children('.inner')

                var buttons = box.find('.zoom-out')
                initButtons(buttons, zoomOut, innerDiv)
                
                var buttons = box.find('.zoom-in')
                initButtons(buttons, zoomIn, innerDiv)
                
                var buttons = box.find('.scroll-to')
                initButtons(buttons, scrollTo)
                
                var buttons = box.find('.scroll-to-input')
                initFields(buttons, scrollTo)

                var controls = box.find('.controls')
                for(var j = 0; j < controls.length; j++)
                {
                    $(controls[j]).show()
                }
            }
		}
	}

	return publicSpace
})()


Tracks.init()
