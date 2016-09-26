var Tooltip = function()
{
    var body = d3.select('body').node()

    var element     // currently shown element (or undefined)
    var tooltip     // tooltip d3js selection object
    var tooltip_content     // tooltip HTML content (result of templating)
    var selection
    var viewport

    var _template = function(d)
    {
        return d.title
    }
    var stuck = false

    function _move(left, top)
    {
        /*
            Why movement is contraint only against right window boundary (tooltip is forced not to exceed width, but not height)?

            First, if we include also height constraint, the tooltip will start jumping over the needle, so it will be hover over and block access (and view) to the needle. It would be very confusing for the end user. Second, detecting height of the screen would require much more calculation and work so it would be slower and more prone to cross-brrowser issues.
        */
        var size = tooltip.node().getBoundingClientRect()

        var viewport_size = viewport.
            getBoundingClientRect()

        left = Math.min(left, viewport_size.right - size.width)
        left = Math.max(left, viewport_size.left)
        top = Math.max(top, viewport_size.top)
        top = Math.min(top, viewport_size.bottom - size.height)

        tooltip
            .style('left', body.scrollLeft + left + 'px')
            .style('top', body.scrollTop + top + 'px')
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

            element = selection
                .filter(function(element){ return checkEquality(element, d) })
                .node()

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

            tooltip.transition()
                .duration(200)
                .style('opacity', 0)
        },
        stick: function(d)
        {
            publicSpace.unstick()
            publicSpace.show(d)
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

            // move to pointer coordinates, as provided by d3 event
            _move(d3.event.clientX, d3.event.clientY)
        },
        moveToElement: function()
        {
            if(!element)
                return

            size = element.getBoundingClientRect()
            // leave 5% uncovered so user will be able to see the element
            _move(size.left + size.width * 0.05, size.top + size.height * 0.05)
        },
        bind: function(new_selection)
        {
            selection = new_selection

            var old_click_event = selection.on('click')
            selection
                .on('click', function(e)
                    {
                        publicSpace.stick(e)
                        old_click_event(e)
                    }
                )
                .on('mouseover', publicSpace.show)
                .on('mousemove', publicSpace.moveToPointer)
                .on('mouseout', publicSpace.hide)

            // do not close the tooltip when selecting
            tooltip
                .on('click', function(){ d3.event.stopPropagation() })

        }
    }

    return publicSpace
}
