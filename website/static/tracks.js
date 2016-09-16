var Tracks = function ()
{

    var minFontSize = 0.1
    var maxFontSize = 20
    var scale = 1.0
    var scrollArea, scalableArea, tracks
    var needle_plot
    var position = 0

    var config = {
        animation: 'swing',
        animations_speed: 200,
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

    function get_scale_factor()
    {
        content_width = scalableArea.get(0).scrollWidth
        width = scalableArea.width()

        return width / content_width
    }

    function _setAAPosition(new_position, stop_callback)
    {
        if(new_position < 0)
            position = 0
        else if(new_position > config.sequenceLength)
            position = config.sequenceLength
        else
            position = new_position

        scrollTo(position)

        if(needle_plot && !stop_callback)
        {
            needle_plot.setAAPosition(position, true)
        }

    }

    function _getZoom()
    {
        first_scale_factor = get_scale_factor()
        return first_scale_factor * scale
    }

    function _setZoom(new_zoom, stop_callback)
    {
        first_scale_factor = get_scale_factor()

		$({area_scale: scale})
			.animate(
				{area_scale: new_zoom},
				{
					duration: config.animations_speed,
					step: function(now)
					{
						scalableArea.css('transform', 'scaleX(' +  first_scale_factor * now + ')')
					}
				}
			)

        scale = new_zoom
        config.char_size = getCharSize(sequence)

        if(needle_plot && !stop_callback)
        {
            needle_plot.setZoom(scale, true)
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
        var old_screen_pos = scrollArea.scrollLeft()
        var one_screen = scrollArea.width() * _getZoom()
        var new_pos_screen = old_screen_pos + one_screen * direction

        _setAAPosition(new_pos_screen / config.char_size, false)
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
        elements.wrapInner('<span></span>')
        var span = elements.children('span')
        var charSize = span.innerWidth() / config.sequenceLength
        span.contents().unwrap()
        return charSize * _getZoom()
    }

    function getSequenceLength()
    {
        var sequence = tracks.find('.sequence')
        var elements = sequence.children('.elements')
        var seq = $.trim(elements.text())
        return seq.length
    }

    function scrollTo(new_position)
    {
        scrollArea.scrollLeft(Math.round(new_position * config.char_size))
    }

	function scrollToCallback()
	{
        var input = $(this).closest('.input-group').find('.scroll-to-input')

        // - 1: sequence is 1 based but position is 0 based
        var pos = $(input).val() - 1

        _setAAPosition(pos, false, true)
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
            tracks = box.find('.tracks')

            scrollArea = tracks.find('.scroll-area')
            scrollArea.on('scroll', function(event)
            {
                var scroll = $(event.target).scrollLeft()
                // is that a meaningful, nonprogramatic scroll?
                if(scroll !== Math.round(position * config.char_size))
                {
                    _setAAPosition(scroll / config.char_size)
                }
            })
            scalableArea = tracks.find('.scalable')

            sequence = tracks.find('.sequence')

            config.sequenceLength = getSequenceLength()
            config.char_size = getCharSize(sequence)

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
            initButtons(buttons, scrollToCallback)

            buttons = box.find('.scroll-to-input')
            initFields(buttons, scrollToCallback)

            var controls = box.find('.controls')
            for(var j = 0; j < controls.length; j++)
            {
                $(controls[j]).show()
            }
            _setZoom(1)

            // initialize all popovers on tracks
            $(function () {
                $('[data-toggle="popover"]').popover(
                    {
                        container: 'body',
                        placement: 'top',
                        trigger: 'hover'
                    }
                )
            })
		},
        setNeedlePlotInstance: function(instance)
        {
            needle_plot = instance
        },
        setZoom: _setZoom,
        setAAPosition: _setAAPosition,
        adjustMaxZoom: function()
        {
            // optimal max zoom is a zoom which allows to zoom in to a normal size of a character
            config.max_zoom = 1 / get_scale_factor()
            return config.max_zoom
        }

	}

	return publicSpace
}
