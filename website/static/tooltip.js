var Tooltip = function()
{
    var body = d3.select('body').node()

    // internals
    var element          // currently shown element (or undefined)
    var tooltip          // tooltip d3js selection object
    var cached_tooltip_size // getting DOM elements dimensions is expensive, hence those are cached
    var tooltip_content  // inner tooltip HTML container
                         // (place where content - result of templating - will be inserted)
    var ignore_next_signal = false; // should next signal be ignored?
    var active = true;

    // configurable
    var viewport
    var preprocess_data
    var data_url    // from where additional data for tooltip should be fetched
    var callback

    // pointer offsets
    var pointerOffsetX = 0
    var pointerOffsetY = 0

    // state
    var stuck = false
    var visible = false


    function addEventListener(selection, type, listener)
    {

        if(selection.empty())
            return

        var old_callback = selection.on(type)

        if(old_callback)
        {
            selection.on(type, function(e)
            {
                // passing `this` context when calling
                old_callback.call(this, e)
                listener.call(this, e)
            })
        }
        else
        {
            selection.on(type, listener)
        }
    }

    var _render_local = function(d)
    {
        tooltip_content.html(
            _template.call(element, d)
        )
        _update_tooltip_size()
    }

    var _render_with_preprocess = function(d)
    {
        tooltip_content.html('Loading...')
        _update_tooltip_size()
        preprocess_data.call(element, d, _render_local)
    }

    var render_template = _render_local

    var _template = function(d)
    {
        return d.title
    }

    var _update_tooltip_size = function () {
        cached_tooltip_size = tooltip.node().getBoundingClientRect()
    }

    function _move(left, top)
    {
        if(!cached_tooltip_size)
            _update_tooltip_size()

        var viewport_size = viewport.getBoundingClientRect()

        left = Math.min(left, viewport_size.right - cached_tooltip_size.width)
        left = Math.max(left, viewport_size.left)
        top = Math.max(top, viewport_size.top)
        top = Math.min(top, viewport_size.bottom - cached_tooltip_size.height)

        var scrollTop = window.pageYOffset || document.documentElement.scrollTop || document.body.scrollTop
        var scrollLeft = window.pageXOffset || document.documentElement.scrollLeft || document.body.scrollLeft

        tooltip
            .style('left', scrollLeft + left + 'px')
            .style('top', scrollTop + top + 'px')
    }


    /**
     * Configuration object for Tooltip.
     * @typedef {Object} Config
     * @property {string} id - REQUIRED identifier for the tooltips to be used in events binding
     * @property {function} template - will be called with data as the only argument, in context of bound element
     * @property {function} callback - to be called after new content is set to the tooltip (after templating)
     * @property {function} preprocess_data - will be called before templating,
     * basically a hook to modify data given to template function.
     * It will be called with data as the first argument and
     * callback to template renderer as the second.
     * Context of bound element will be provided.
     * @property {HTMLElement} viewport - element to which the maximal size/position of tooltips
     should restricted. If not given, defaults to body (so tooltips
     are always visible on the user's screen).

     Using body as a viewport requires following css declarations:
         html{height:100%} body{min-height:100%}
     */

    var publicSpace = {
        /** Initialize tooltip class
         * @param {Config} config
         */
        init: function(config)
        {
            tooltip = d3.select('body')
                .append('div')
                .attr('class', 'tooltip popover')
                .style('opacity', 0)
                .style('pointer-events', 'none')

            var wrapper = tooltip
                .append('div')
                .attr('class', 'wrapper')

            tooltip_content = wrapper
                .append('div')
                .attr('class', 'popover-content')

            if(config.template)
                _template = config.template

            if(config.callback)
                callback = config.callback

            d3.select('body')
                .on('mouseup.' + config.id, publicSpace.unstick)

            // create a close button
            wrapper.append('button')
                .attr('class', 'close')
                .html('x')
                .on('click', publicSpace.unstick)

            if(config.viewport)
                viewport = config.viewport
            else
                viewport = body

            if(config.preprocess_data)
            {
                preprocess_data = config.preprocess_data
                render_template = _render_with_preprocess
            }
        },
        show: function(d)
        {
            if(ignore_next_signal)
            {
                ignore_next_signal = false
                return
            }
            if(!active)
                return

            if(stuck)
                return

            if(element != this)
            {
                // `d` provides data whereas `this` gives the DOM element
                element = this
                // re-render template only on if the element has changed
                render_template(d)

                if(callback)
                    callback(tooltip_content.node())
            }

            publicSpace.moveToPointer()

            tooltip.transition()
                .duration(50)
                .style('opacity', 1)

            visible = true
        },
        hide: function(keep_element)
        {
            if(stuck || !visible)
                return

            tooltip.transition()
                .duration(200)
                .style('opacity', 0)

            if(!keep_element)
                element = null

            visible = false
        },
        ignore_next_signal: function()
        {
            ignore_next_signal = true;
        },
        active: function(value)
        {
            active = value
        },
        stick: function(d)
        {
            if(ignore_next_signal)
            {
                ignore_next_signal = false
                return
            }
            if (d3.event.defaultPrevented) return
            publicSpace.unstick()
            // call `show` method passing `this` context
            publicSpace.show.call(this, d)
            tooltip.style('pointer-events', 'auto')
            stuck = true
            d3.event.stopPropagation()
        },
        unstick: function()
        {
            stuck = false
            publicSpace.hide(true)
            tooltip.style('pointer-events', 'none')
        },
        moveToPointer: function()
        {
            if(stuck || !visible)
                return

            var size = element.getBoundingClientRect()
            pointerOffsetX = d3.event.clientX - size.left
            pointerOffsetY = d3.event.clientY - size.top

            // move to pointer coordinates, as provided by d3 event
            _move(d3.event.clientX, d3.event.clientY)
        },
        moveToElement: function()
        {
            if(!element || !visible)
                return

            var size = element.getBoundingClientRect()
            _move(size.left + pointerOffsetX, size.top + pointerOffsetY)
        },
        bind: function(selection)
        {
            addEventListener(selection, 'click', publicSpace.stick)
            addEventListener(selection, 'mouseover', publicSpace.show)
            addEventListener(selection, 'mousemove', publicSpace.moveToPointer)
            addEventListener(selection, 'mouseout', publicSpace.hide)

            // do not close the tooltip when selecting
            tooltip
                .on('mouseup', function(){ d3.event.stopPropagation() })

            // update size and position if clicked (assuming that a click is only action which can change size,
            // e.g. while clicking on "more" or "less" buttons.
            tooltip
                .on('click', function(){
                    // after size-changing handler execution
                    setTimeout(function() {
                        _update_tooltip_size()
                        publicSpace.moveToElement()
                    }, 0)
                })


        }
    }

    return publicSpace
}
