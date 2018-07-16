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
    var controls, box
    var is_animation_running
    var tooltip

    var config = {
        scroll_step: 0.8, // how many screen (to left or right) should be scrolled after clicking scroll button
        zoom_step: 2,
        zoom_speed: 100,
        animations_speed: 300,
        animations_ease: 'quad',
        box: null,
        min_zoom: 1,
        max_zoom: 10
    };

    function configure(new_config)
    {
        // Automatic configuration update:
        update_object(config, new_config)
    }

    function calculate_zoom(direction)
    {
        // scale down slower toward 0
        var new_zoom = scale + direction * scale / 15;

        if(new_zoom > config.max_zoom)
        {
            return config.max_zoom
        }
        else if(new_zoom < config.min_zoom)
        {
            return config.min_zoom
        }
        else
        {
            return new_zoom
        }
    }

    function get_scale_factor()
    {
        var content_width = scalableElem.scrollWidth;
        var width = scalableArea.width();

        return width / content_width
    }

    function _setAAPosition(new_position, stop_callback, update_zoom)
    {
        position = trim_position(new_position)

        scrollTo(position)

        if(update_zoom)
            _setZoom(scale, true)

        if(!stop_callback && needle_plot)
        {
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
        return _setZoomAndMove(new_zoom, _getAAPosition(), stop_callback, true)
    }

    function trim_position(new_position, new_zoom, skip_zoom_effect)
    {
        if(new_position < 0)
            return 0
        else {
            var end = config.sequenceLength

            if(!skip_zoom_effect)
                end -= _visibleAminoacidsCount(new_zoom)

            if(new_position > end)
                return end
            else
                return new_position
        }
    }

    function _setZoomAndMove(new_zoom, new_pos, stop_callback, skip_animation, center_view)
    {
        new_pos = trim_position(new_pos, new_zoom)

        var styles = scalableElem.style;

        var invoke_callback = (!stop_callback && needle_plot)

        var initial_scale = scale

        var step = function(now, fx)
        {
            if(fx.prop === 'p')
            {
                if(center_view)
                    return

                position = now
                scrollTo(position)
                return
            }

            scale = now
            config.char_size = getCharSize()

            if(center_view)
            {
                // as I want the chosen aminoacid to remain in place when zooming:
                // central = first_visible + visible_count / 2
                // I use the central before zoom and central after zoom to find
                // the first_visible_after_zoom which satisfies condition: central=const
                // new_pos is the first visible aminoacid to be targeted,
                // position is the first visible aminoacid to be shown in this step
                position = new_pos + _visibleAminoacidsCount() / 2 * (1 - initial_scale / scale)
            }

            styles.transform = 'scaleX(' +  first_scale_factor * scale + ')'
            scrollTo(position)

            if(invoke_callback)
                needle_plot.setZoomAndAAPosition(scale, position, true)

        }

        is_animation_running = true
        $({s: scale, p: position})
            .animate(
                {s: new_zoom, p: new_pos},
                {
                    duration: skip_animation ? 0 : config.zoom_speed,
                    ease: config.animations_ease,
                    queue: false,
                    step: step,
                    complete: function() {
                        dispatch.zoomAndMove(this)
                        is_animation_running = false
                    }
                }
            )

    }

    function zoomKeepingCentral(direction)
    {
        var zoom = calculate_zoom(direction)
        var first_visible_aa = _getAAPosition()
        _setZoomAndMove(zoom, first_visible_aa, false, false, true)
    }

    function zoomIn()
    {
        zoomKeepingCentral(+config.zoom_step)
    }

    function zoomOut()
    {
        zoomKeepingCentral(-config.zoom_step)
    }

    function _getAAPosition()
    {
        return position
    }

    function _visibleAminoacidsCount(scale_to_use)
    {
        return config.min_zoom * config.sequenceLength / (scale_to_use ? scale_to_use : scale)
    }

    /**
     * Move by one screen in given direction
     * @param direction - move one screen right if +1, one screen left if -1
     * @param {boolean} animate - should the scrolling be animated?
     */
    function scroll(direction, animate)
    {
        var new_pos_screen = _getAAPosition() + _visibleAminoacidsCount() * direction
        new_pos_screen = trim_position(new_pos_screen)

        if(new_pos_screen === position)
            return

        is_animation_running = true
        $({screen_position: position})
            .animate(
                {screen_position: new_pos_screen},
                {
                    duration: animate ? config.animations_speed : 0,
                    ease: config.animations_ease,
                    queue: false,
                    step: function(now)
                    {
                        position = now
                        scrollTo(now)
                        needle_plot.setAAPosition(now, true)
                        dispatch.zoomAndMove(this)
                    },
                    complete: function() {
                        is_animation_running = false
                    }
                }
            )
    }

    function scrollLeft()
    {
        scroll(-config.scroll_step, true)
    }

    function scrollRight()
    {
        scroll(+config.scroll_step, true)
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
        scrollArea.scrollLeft(new_position * config.char_size)
    }

    function parsePosition(position_string)
    {
        if(position_string === undefined)
            return undefined
        return trim_position(parseInt(position_string, 10), undefined, true)
    }

    function scrollToCallback()
    {
        var input = $('.scroll-to-input')

        // - 1: sequence is 1 based but position is 0 based
        var user_input = $(input).val()

        var pos
        var zoom

        var correct_expression = /^\s*(\d+)\s*([-|:]\s*(\d+))?\s*$/

        var matched_range = user_input.match(correct_expression)
        var feedback = $('.scroll-feedback')

        function warn() {
            feedback.html('<span class="glyphicon glyphicon-warning-sign"></span>')
        }

        if(matched_range)
        {
            // get range
            var range = [matched_range[1], matched_range[3]]

            // convert to int, trim if the values exceed protein length or 0
            range = range.map(parsePosition)

            // make first coordinate 0-based
            pos = range[0] - 1

            // if we have both parts of expression (two numbers)
            if(range[1] !== undefined)
            {
                var len = range[1] - range[0]

                // if user provides range with the second value being smaller,
                // it may be good to warn the user; moreover we do not want to
                // divide by zero.
                if(len < 1)
                    return warn()

                // calculate zoom such that we will see only the desired range
                zoom = config.min_zoom * config.sequenceLength / len

                // and trim it to max allowed zoom
                zoom = Math.min(zoom, config.max_zoom)
            }
            else
            {
                // zoom in as close to the mutation as we can get
                zoom = config.max_zoom

                // move the position to the center
                pos -= _visibleAminoacidsCount(zoom) / 2
            }
            // clear the feedback (the empty string is important!)
            feedback.html('')
        }
        else
        {
            // incorrect input
            warn()
        }

        // zoom and move: run callback, animate, do not attempt to center on given position
        _setZoomAndMove(zoom, pos, false, false, false)
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

    function initControls()
    {
        var buttons = controls.find('.scroll-left')
        initButtons(buttons, scrollLeft, scrollArea)

        buttons = controls.find('.scroll-right')
        initButtons(buttons, scrollRight, scrollArea)

        var innerDiv = box.children('.inner')

        buttons = controls.find('.zoom-out')
        initButtons(buttons, zoomOut, innerDiv)

        buttons = controls.find('.zoom-in')
        initButtons(buttons, zoomIn, innerDiv)

        buttons = controls.find('.scroll-to')
        initButtons(buttons, scrollToCallback)

        buttons = controls.find('.scroll-to-input')
        initFields(buttons, scrollToCallback)
    }

    function onManualScroll(event)
    {
        var scroll = $(event.target).scrollLeft()

        if(!is_animation_running)
        {
            _setAAPosition(scroll / config.char_size, false)
        }
    }

    var publicSpace = {
        init: function(new_config)
        {
            configure(new_config)

            box = $(config.box)
            tracks = box.find('.tracks')

            scrollArea = tracks.find('.scroll-area')
            scrollArea.on('scroll', onManualScroll)
            scalableArea = tracks.find('.scalable')
            scalableElem = scalableArea.get(0)

            var sequence = tracks.find('.sequence')
            sequence_elements = sequence.children('.elements')

            var conservation = tracks.find('.conservation')
            var scores = conservation.find('i')

            var values = scores.map(function(i, obj){
                return parseFloat($(this).attr('v'))
            })

            var min = Math.min.apply(null, values)
            var max = Math.max.apply(null, values)
            scores.each(function(i, obj)
            {
                var obj = $(this)
                var value = parseFloat(obj.attr('v'))
                var text = value + ': '
                if(value >= 0){
                    var r = 255 - (value / max * 255)
                    obj.css('background', 'rgb(255, ' + r + ', ' + r + ')')
                    text += 'conserved'
                }
                else {
                    obj.css('background', 'rgb(' + (255 - (value / min * 255)) + ', 255, 255)')
                    text += 'accelerated'
                }
                obj.attr('title', text)
            })


            config.sequenceLength = getSequenceLength()
            config.char_size = getCharSize()

            controls = $($.find('.tracks-controls'))

            initControls()

            publicSpace.refreshScaleFactor()

            _setZoom(1)

            // initialize all popovers on tracks
            tooltip = Tooltip()
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

            publicSpace.show()

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
        },
        hide: function()
        {
            box.find('.tracks-box').addClass('invisible');
            controls.addClass('invisible');

            if(config.animations_speed)
                box.animate({height: 0}, config.animations_speed);
        },
        show: function()
        {
            var internal_box = box.find('.tracks-box');
            internal_box.removeClass('invisible');
            controls.removeClass('invisible');

            if(config.animations_speed)
                box.animate(
                    {height: internal_box.height()},
                    {
                        duration: config.animations_speed,
                        complete: function () {
                            // reset to original value (so domains can be expanded)
                            box.css('height', '')
                        }
                    }
                );
        },
        scrollTo: function (position) {
            $('.scroll-to-input').val(position)
            scrollToCallback();
        },
        destroy: function ()
        {
            if(tooltip) tooltip.remove()
        }

    }

    return publicSpace
}
