var Tooltip = function()
{
    var body = d3.select('body').node()

    // internatls
    var element     // currently shown element (or undefined)
    var tooltip     // tooltip d3js selection object
    var tooltip_content     // inner tooltip HTML container (place where content - result of templating - will be inserted)

    // configurable
    var viewport

    // pointer offsets
    var pointerOffsetX = 0
    var pointerOffsetY = 0

    // state
    var stuck = false

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

    var _template = function(d)
    {
        return d.title
    }

    function _move(left, top)
    {
        var size = tooltip.node().getBoundingClientRect()

        var viewport_size = viewport.getBoundingClientRect()

        left = Math.min(left, viewport_size.right - size.width)
        left = Math.max(left, viewport_size.left)
        top = Math.max(top, viewport_size.top)
        top = Math.min(top, viewport_size.bottom - size.height)

        var scrollTop = window.pageYOffset || document.documentElement.scrollTop || document.body.scrollTop
        var scrollLeft = window.pageXOffset || document.documentElement.scrollLeft || document.body.scrollLeft

        tooltip
            .style('left', scrollLeft + left + 'px')
            .style('top', scrollTop + top + 'px')
    }

    var publicSpace = {
        init: function(custom_template, id, custom_viewport)
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

            if(custom_template !== undefined)
            {
                _template = custom_template
            }
            d3.select('body')
                .on('click.' + id, publicSpace.unstick)

            // create a close button
            wrapper.append('button')
                .attr('class', 'close')
                .html('x')
                .on('mouseup', publicSpace.unstick)

            if(custom_viewport)
                viewport = custom_viewport
            else
                viewport = body
        },
        show: function(d)
        {
            if(stuck)
                return

            // `d` provides data whereas `this` gives the DOM element
            element = this

            tooltip.transition()
                .duration(50)
                .style('opacity', 1)
            tooltip_content.html(_template(d))

            publicSpace.moveToPointer()
        },
        hide: function(v)
        {
            if(stuck)
                return

            element = null

            tooltip.transition()
                .duration(200)
                .style('opacity', 0)
        },
        stick: function(d)
        {
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
            if(stuck)
                return

            size = element.getBoundingClientRect()
            pointerOffsetX = d3.event.clientX - size.left
            pointerOffsetY = d3.event.clientY - size.top

            // move to pointer coordinates, as provided by d3 event
            _move(d3.event.clientX, d3.event.clientY)
        },
        moveToElement: function()
        {
            if(!element)
                return

            size = element.getBoundingClientRect()
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
                .on('click', function(){ d3.event.stopPropagation() })

        }
    }

    return publicSpace
}
