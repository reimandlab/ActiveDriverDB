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

            tooltip
                .style('left', (d3.event.pageX) + 'px')
                .style('top', (d3.event.pageY - 28) + 'px')
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
