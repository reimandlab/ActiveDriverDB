var Tooltip = function()
{
    var tooltip
    var tooltip_content

    var _template = function(d)
    {
        return d.title
    }
    var stuck = false

    var publicSpace = {
        init: function(custom_template, id)
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
        },
        show: function(d)
        {
            if(stuck)
                return

            tooltip.transition()
                .duration(50)
                .style('opacity', 1)
            tooltip_content.html(_template(d))

            publicSpace.move()
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
        move: function()
        {
            if(stuck)
                return

            /*
                Why movement is contraint only against right window boundary (tooltip is forced not to exceed width, but not height)?

                First, if we include also height constraint, the tooltip will start jumping over the needle, so it will be hover over and block access (and view) to the needle. It would be very confusing for the end user. Second, detecting height of the screen would require much more calculation and work so it would be slower and more prone to cross-brrowser issues.
            */
            var size = tooltip.node().getBoundingClientRect()

            var body_size = document.
                getElementsByTagName('body')[0].
                getBoundingClientRect()

            var left = d3.event.pageX

            if(size.width + left > body_size.width)
                left -= size.width + left - body_size.width

            tooltip
                .style('left', left + 'px')
                .style('top', d3.event.pageY + 'px')
        },
        bind: function(selection)
        {
            selection
                .on('click', publicSpace.stick)
                .on('mouseover', publicSpace.show)
                .on('mousemove', publicSpace.move)
                .on('mouseout', publicSpace.hide)

            // do not close the tooltip whene selecting
            tooltip
                .on('click', function(){ d3.event.stopPropagation() })

        }
    }

    return publicSpace
}
