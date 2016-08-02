var Tracks = function ()
{

    var minFontSize = 0.1
    var maxFontSize = 20
    var scale = 1.0
    var scrollArea
    var scalableArea
    var needle_plot

    var config = {
        animations_speed: 300,
        box: null,
		min_zoom: 1,
        max_zoom: 10

    }

    function configure(new_config)
    {
        // Automatical configuration update:
        update_object(config, new_config)
    }

    function zoom(direction)
    {
        // scale down slower toward 0
        new_zoom = scale + direction * scale / 15

        if(new_zoom > config.max_zoom)
        {
            _setZoom(config.max_zoom)
        }
        else if(new_zoom < config.min_zoom)
        {
            _setZoom(config.min_zoom)
        }
        else
        {
            _setZoom(new_zoom)
        }
    }

    function _setZoom(new_zoom, stop_callback)
    {
        content_width  = scalableArea.get(0).scrollWidth
        width = scalableArea.width()

		$({scale: scale})
			.animate(
				{scale: new_zoom},
				{
					duration: config.animations_speed,
					step: function(now)
					{
						scalableArea.css('transform', 'scaleX(' + width / content_width * now + ')')
					}
				}
			)

        scale = new_zoom

        if(needle_plot && !stop_callback)
        {
            needle_plot.setZoom(scale, false)
        }
    }

    function zoomIn()
    {
        zoom(+1)
    }

    function zoomOut()
    {
        zoom(-1)
    }

    function scroll(direction)
    {
        var pos = scrollArea.scrollLeft()
        var len = scrollArea.width()

        scrollArea
			.stop()
			.animate(
				{scrollLeft: pos + len * direction },
				config.animations_speed,
				'quad'
			)
    }

	function scrollLeft()
	{
        scroll(-1)
	}

	function scrollRight()
	{
        scroll(+1)
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
        var sequence = tracks.find('.sequence')
        // - 1: sequence is 1 based but position is 0 based
        var pos = $(input).val() - 1

        var charSize = getCharSize(sequence)
        area.animate({scrollLeft: pos * charSize }, config.animations_speed, 'quad')
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
        function call(e)
        {
            if(e.keyCode === 13)
            {
                func.call(this)
            }
        }

        for(var i = 0; i < fields.length; i++)
        {
            $(fields[i]).keyup(call)
        }
    }

	var publicSpace = {
		init: function(new_config)
		{
			configure(new_config)
            var box = $(config.box)

            var tracks = box.find('.tracks')

            scrollArea = tracks.find('.scroll-area')
            scalableArea = tracks.find('.scalable')

            var buttons = box.find('.scroll-left')
            initButtons(buttons, scrollLeft, scrollArea)

            buttons = box.find('.scroll-right')
            initButtons(buttons, scrollRight, scrollArea)

            var innerDiv = box.children('.inner')

            buttons = box.find('.zoom-out')
            initButtons(buttons, zoomOut, innerDiv)

            buttons = box.find('.zoom-in')
            initButtons(buttons, zoomIn, innerDiv)

            buttons = box.find('.scroll-to')
            initButtons(buttons, scrollTo)

            buttons = box.find('.scroll-to-input')
            initFields(buttons, scrollTo)

            var controls = box.find('.controls')
            for(var j = 0; j < controls.length; j++)
            {
                $(controls[j]).show()
            }
            _setZoom(1)
		},
        setNeedlePlotInstance: function(instance)
        {
            needle_plot = instance
        },
        setZoom: _setZoom
	}

	return publicSpace
}
