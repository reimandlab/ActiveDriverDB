var Tracks = function ()
{
    var scale = 1.0
    var scrollArea, scalableArea, scalableElem, tracks
    var needle_plot
    var position = 0
    var dispatch = d3.dispatch('zoomAndMove')
    var first_scale_factor
    var sequence_elements, baseCharSize
    var is_ready = false

    var config = {
        animation: 'swing',
        animations_speed: 200,
        box: null,
        min_zoom: 1,
        max_zoom: 10
    };

    function configure(new_config)
    {
        // Automatic configuration update:
        update_object(config, new_config)
    }

    function zoom(direction)
    {
        // scale down slower toward 0
        var new_zoom = scale + direction * scale / 15;

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
        var content_width = scalableElem.scrollWidth;
        var width = scalableArea.width();

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

        if(!stop_callback && needle_plot)
        {
            _setZoom(scale, true)
            needle_plot.setAAPosition(position, true)
        }
        dispatch.zoomAndMove(this)

    }

    function _getZoom()
    {
        return first_scale_factor * scale
    }

    function _setZoom(new_zoom, stop_callback)
    {
        var styles = scalableElem.style;
        $({scale: scale})
            .animate(
                {scale: new_zoom},
                {
                    duration: config.animations_speed,
                    step: function(now)
                    {
                        styles.transform = 'scaleX(' +  first_scale_factor * now + ')'
                    }
                }
            )

        scale = new_zoom
        config.char_size = getCharSize()

        if(!stop_callback && needle_plot)
        {
            _setAAPosition(position, true)
            needle_plot.setZoom(scale, true)
        }
        dispatch.zoomAndMove(this)

    }

    function _setZoomAndMove(new_zoom, new_pos, stop_callback)
    {
        _setZoom(new_zoom, false)
        _setAAPosition(new_pos, false)

        dispatch.zoomAndMove(this)
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

    function computeBaseCharSize()
    {
        sequence_elements.wrapInner('<span></span>');
        var span = sequence_elements.children('span');
        var charSize = span.innerWidth() / config.sequenceLength;
        span.contents().unwrap();
        return charSize;
    }

    function getCharSize()
    {
        return baseCharSize * _getZoom();
    }

    function getSequenceLength()
    {
        var seq = $.trim(sequence_elements.text())
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
                // is that a meaningful, non-programmatic scroll?
                if(scroll !== Math.round(position * config.char_size))
                {
                    _setAAPosition(scroll / config.char_size)
                }
            })
            scalableArea = tracks.find('.scalable')
            scalableElem = scalableArea.get(0)

            sequence = tracks.find('.sequence')
            sequence_elements = sequence.children('.elements')

            config.sequenceLength = getSequenceLength()
            config.char_size = getCharSize()

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
            publicSpace.refreshScaleFactor()

            _setZoom(1)

            // initialize all popovers on tracks
            var tooltip = Tooltip()
            tooltip.init({
                id: 'tracks',
                template: function(data){
                    var elem = $(this)
                    var templated = (
                        '<h5>' + elem.data('title') + '</h5>' +
                        elem.data('content')
                    )
                    return templated
                },
                viewport: scrollArea.get(0)
            })

            var kinases = d3.selectAll('.has-tooltip')
                .each(function(data){
                    // if we add tooltips, let's remove original title tooltip
                    // and reuse this data in the new tooltip
                    $(this).data('title', this.title)
                    this.title = ''
                })
                .call(tooltip.bind)

            dispatch.on('zoomAndMove', function(){
                tooltip.moveToElement()
            })

            $('.subtracks_collapsed').click(function(){
                var track_name = $(this).data('track');
                $('.' + track_name + ' .collapsible').toggleClass('hidden')
            })

            is_ready = true;
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
            config.max_zoom = 1 / first_scale_factor
            return config.max_zoom
        },
        setZoomAndMove: _setZoomAndMove,
        refreshScaleFactor: function()
        {
            first_scale_factor = get_scale_factor();
            baseCharSize = computeBaseCharSize();
        },
        isReady: function()
        {
            return is_ready;
        }

    }

    return publicSpace
}
