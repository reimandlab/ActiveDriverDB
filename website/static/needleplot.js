var Tooltip = function()
{
    var tooltip

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
                .attr('class', 'tooltip')
                .style('opacity', 0)
                .style('pointer-events', 'none')
            if(custom_template !== undefined)
            {
                _template = custom_template
            }
            d3.select('body')
                .on('click.' + id, publicSpace.unstick)
        },
        show: function(d)
        {
            if(stuck)
                return

            tooltip.transition()
                .duration(50)
                .style('opacity', 1)
            tooltip.html(_template(d))
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
            stuck = true
            d3.event.stopPropagation()
        },
        unstick: function()
        {
            stuck = false
            publicSpace.hide(true)
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
        }
    }

    return publicSpace
}

var NeedlePlot = function ()
{
    var svg, zoom, vis, vertical_scalable, unit
    var scale = 1
	var position = 0

    var legend = {
        x:
        {
            obj: null
        },
        y:
        {
            obj: null
        }
    }

    var Axis = function()
    {
        return {
            scale: null,
            group: null,
            obj: null
        }
    }

    var axes = {
        x: new Axis(),
        y: new Axis()
    }

    var config = {
        use_log: false, // should logaritmic (base 10) scale by used instead of linear?
        value_type: 'Count', // count or frequency
        site_height: 10,
        animations_speed: 200,
        // 90 is width of description
        paddings: {bottom: 40, top: 30, left: 89, right: 1},
        y_scale: 'auto',
        sequenceLength: null,
        element: null,
        mutations: null,
        sites: null,
        needles: null,
        legends: {x: 'Sequence', y: '# of mutations'},
        width: 600,
        height: null,
        zoom_callback: null,
        position_callback: null,
        ratio: 0.5,
        min_zoom: 1,
        max_zoom: 10,
        color_map: {
          'distant': 'yellow',
          'network-rewiring': 'red',
          'direct': 'darkred',
          'proximal': 'orange',
          'none': 'darkgray'
        }
    }

	function get_remote_if_needed(new_config, name)
	{
        if(typeof new_config[name] === 'string')
        {
			$.ajax({
				url: new_config[name],
				type: 'GET',
				async: false,
				success: function(data)
				{
					new_config[name] = data
				}
			})
        }
	}

    function _adjustPlotDimensions()
    {
        if(!config.width && !config.height)
        {
            config.width = config.sequenceLength
        }

        if(config.height && config.width)
        {
            config.ratio = config.height / config.width
        }
        else if(!config.height)
        {
            config.height = config.width * config.ratio
        }
        else if(!config.width)
        {
            config.height = config.width * config.ratio
        }
    }

    function configure(new_config)
    {
		var allowed_remote_data = ['mutations', 'sites']

		for(var i = 0; i < allowed_remote_data.length; i++)
		{
			var name = allowed_remote_data[i]
			get_remote_if_needed(new_config, name)
		}

        // Automatical configuration update:
        update_object(config, new_config)

        // Manual configuration patching:
        _adjustPlotDimensions()

    }

    function scaleToNeedles()
    {
		if (config.y_scale === 'auto')
		{
            var accessor = function(mutation) {
                return mutation.value
            }
			config.y_scale_max = d3.max(config.mutations, accessor)
			config.y_scale_min = d3.min(config.mutations, accessor)
		}
    }

    function _rescalePlot()
    {
        svg
            .attr('viewBox', '0 0 ' + config.width + ' ' + config.height)

		unit = (config.width - config.paddings.left - config.paddings.right) / config.sequenceLength

        axes.x.scale
            .range([0, config.width - config.paddings.left - config.paddings.right])

        axes.y.scale
            .range([config.height - config.paddings.top - config.site_height, config.paddings.bottom])

        axes.y.obj.scale(axes.y.scale)
        axes.y.group.call(axes.y.obj)

		var bottom_axis_pos = config.height - config.paddings.bottom

        axes.x.obj
            .scale(axes.x.scale)
            .tickSize(config.site_height + 3)

        axes.x.group
	        .attr('transform', 'translate(' + [0, bottom_axis_pos] + ')')
            .call(axes.x.obj)

        sites
            .attr('transform', function(d)
                {
                    return 'translate(' + [posToX(d.start), bottom_axis_pos] + ')'
                }
            )

        site_boxes
			.attr('width', function(d){ return posToX(d.end - d.start) })

        needles
            .attr('transform', function(d)
                {
                    return 'translate(' + [posToX(d.coord), 0] + ')'
                }
            )

        needles.selectAll('line')
            .attr('stroke-width', posToX(1) / 2 + 'px')
            .attr('y1', function(d){ return axes.y.scale(d.value) + 'px' })
            .attr('y2', bottom_axis_pos + 'px')

        leftPadding.attr('height', config.height)

        if(legend.x.obj)
            legend.x.obj.attr('x', config.width / 2)
        if(legend.y.obj)
            legend.y.obj.attr('transform','translate(' + -(config.paddings.left - 15) + ' ' + config.height / 2 + ') rotate(-90)')

        adjustContent()
    }

    function append_group(selection, class_name)
    {
        selection
            .append('g')
            .attr('class', class_name)
    }

    function createPlot()
    {
        zoom = d3.behavior.zoom()
            .scaleExtent([config.min_zoom, config.max_zoom])
            .on('zoom', zoomAndMove)


        svg = d3.select(config.element).append('svg')
            .attr('preserveAspectRatio', 'xMinYMin meet')
            .attr('class', 'svg-content-responsive')
            .call(zoom)

		paddings = svg.append('g')
			.attr('class', 'paddings')
			.attr('transform', 'translate(' + config.paddings.left + ' , 0)')

		vertical_scalable = paddings.append('g')
			.attr('class', 'vertical scalable')

        leftPadding = paddings.append('rect')
            .attr('fill', 'white')
            .attr('width', config.paddings.left)
			.attr('transform', 'translate(-' + config.paddings.left + ' , 0)')

        if(config.use_log)
        {
            axes.y.scale = d3.scale.log()
                .base(10)
                // we have to avoid exact 0 on scale_min
                .domain([config.y_scale_min || Number.MIN_VALUE, config.y_scale_max])

            var cnt = -1
            var labels_count_in_log = config.height / 40
            var ticks_cnt = axes.y.scale.ticks().length
            config.log_ticks_per_label = Math.round(ticks_cnt / labels_count_in_log)

            function log_ticks_format(d){
                cnt += 1

                if(cnt % config.log_ticks_per_label !== 0)
                    return ''

                d /= 100
                if(d < 0.0001)
                    return d3.format('.3%')(d)
                if(d < 0.001)
                    return d3.format('.2%')(d)
                if(d < 0.01)
                    return d3.format('.1%')(d)
                return d3.format('%')(d)
            }

        }
        else
        {
            axes.y.scale = d3.scale.linear()
                .domain([0, config.y_scale_max])
        }

        axes.y.scale.
            nice()

        axes.y.obj = d3.svg.axis()
            .orient('left')
            .scale(axes.y.scale)

        var format = !config.use_log ? d3.format('d') : log_ticks_format
        var sub_div = !config.use_log ? 0 : 5

        axes.y.obj
            .ticks(10)
            .tickFormat(format)
            //.tickSubdivide(sub_div)

        axes.y.group = paddings.append('g')
			.attr('class', 'y axis')
            .call(axes.y.obj)

        axes.x.scale = d3.scale.linear()
            .domain([0, config.sequenceLength])

        axes.x.obj = d3.svg.axis()
            .orient('bottom')
            .scale(axes.x.scale)

        axes.x.group = paddings.append('g')
			.attr('class', 'x axis')
            .call(axes.x.obj)

        vis = vertical_scalable.append('g')

        if(config.legends.x)
        {
            legend.x.obj = paddings.append('text')
                .attr('class', 'label')
                .text(config.legends.x)
                .attr('x', config.width / 2)
                .attr('y', config.height - config.paddings.bottom)
                .attr('dy','2.4em')
                .style('text-anchor','middle')
        }

        if(config.legends.y)
        {
            legend.y.obj = paddings.append('text')
                .attr('class', 'label')
                .text(config.legends.y)
                .style('text-anchor','middle')
        }

        var needle_tooltip = Tooltip()
        needle_tooltip.init(
            function(d){
                var text = 'PTM type: ' + d.category + '<br>' +
                           'Position: ' + d.coord + '<br>' +
                           config.value_type + ': ' + d.value + '<br>' +
                           'Alt residue: ' + d.alt

               for(var meta in d.meta)
               {
                   text += '<br>' + meta + ':'
                   text += '<ul>'
                   for(var column in d.meta[meta])
                   {
                       text += '<li>' + column + ': ' + d.meta[meta][column]
                   }
                   text += '</ul>'
               }
                return text
            },
            'needle'
        )

        needles = vis.selectAll('.needle')
            .data(config.mutations)
            .enter()
            .append('g')
            .attr('class', 'needle')
            .call(needle_tooltip.bind)

        needles
            .append('line')
                .attr('x1', 0)
                .attr('x2', 0)

        needles
            .append('circle')
                .attr('fill', function(d)
                    {
                        return config.color_map[d.category]
                    }
                )

        var site_tooltip = Tooltip()

        site_tooltip.init(
            function(d){
                return d.type + '<br>' + (d.start + 7)
            },
            'site'
        )

        sites = vis.selectAll('.site')
            .data(config.sites)
            .enter()
            .append('g')
            .attr('class', function(d)
                {
                    if(d.type.indexOf(',') === -1)
                        return 'site '+ d.type
                    else
                        return 'site multi_ptm'
                }
            )
            .call(site_tooltip.bind)

        site_boxes = sites
			.append('rect')
			.attr('height', config.site_height)

        sites
            .append('path')
            .attr('d', d3.svg.symbol().size(4).type('triangle-up'))

        _rescalePlot()

    }

	function _setPosition(new_position, stop_callback)
	{
        var axis_coverage = xAxisCoverage()
		var boundary = posToX(axis_coverage - config.sequenceLength) * scale

		if(new_position > 0)
			position = 0
		else if(new_position < boundary)
			position = boundary
		else
			position = new_position

        // let d3 know that we changed the position
        zoom.translate([position, 0])

        if(!stop_callback && config.position_callback)
        {
            aa_position = xToPos(position)
            config.position_callback(aa_position, true)
        }
	}


    function canvasAnimated(animate)
    {
        if(animate)
        {
		    t = svg
			    .transition().ease('quad').duration(config.animations_speed)
        }
        else
        {
            t = svg
        }
        return t
    }

    function adjustContent(animate)
    {
        if(scale == config.max_zoom)
        {
            axes.x.obj.ticks(20)
        }
        else if(axes.x.obj.ticks() != 10)
        {
            axes.x.obj.ticks(10)
        }

        var canvas = canvasAnimated(animate)
		canvas.select('.vertical.scalable').attr('transform', 'translate(' + position + ', 0)scale(' + scale + ', 1)')

        needles.selectAll('circle')
            .attr('transform', function(d){ return 'translate('  + [0, axes.y.scale(d.value)] + ')scale(1, '+ scale +') ' })

        site_boxes.
            attr('stroke-width', 1/scale + 'px')

        sites.selectAll('path')
            .attr('transform', function(d)
                {
                    // shift by -2 in yaxis is meant to lay the shape
                    // on top of site box (it's size_of_shape/2 = 4/2 = 2)
                    return 'translate(' + [posToX((d.end - d.start) / 2), -2] + ')scale(' + [1, posToX(1)] + ')'
                }
            )

        needles.selectAll('circle')
            .attr('r', posToX(1) / 2 * (config.max_zoom / scale) + 'px')
    }

    function xAxisCoverage()
    {
        return config.sequenceLength / scale
    }

	function posToX(pos)
	{
		return pos * unit
	}

    function xToPos(coord)
    {
        return -(coord / unit) / scale
    }

    function adjustXAxis(animate)
    {
        var canvas = canvasAnimated(animate)
        var axis_coverage = xAxisCoverage()
        var start = xToPos(position)
		axes.x.scale.domain([start, start + axis_coverage])
		canvas.select('.x.axis').call(axes.x.obj)
    }

    function refresh(animate)
    {
        adjustXAxis(animate)
        adjustContent(animate)
    }

    function zoomAndMove()
    {
		_setZoomAndMove(d3.event.scale, d3.event.translate[0])
    }

    function _setZoomAndMove(new_scale, new_position, animate)
    {
		_setZoom(new_scale)
		_setPosition(new_position)

        refresh(animate)
    }

	function _setZoom(new_scale, stop_callback)
	{
        if(scale === new_scale)
            return

		scale = new_scale

        // if we have a callback, release it (unless explicitly asked to refrain)
        if(!stop_callback && config.zoom_callback)
        {
            config.zoom_callback(scale, true)
        }
        // if we are not issung a callback, that the function was called by callback,
        // then we want to assure that all related components are aware of zoom update
        else
        {
            // let d3 know that the zoom was changed
			zoom.scale(scale)

            // recalculate position so we do not exceed boundaries
            _setPosition(position)

            // adjust axes
            refresh(true)
        }

	}

    var publicSpace = {
        init: function(new_config)
        {
            configure(new_config)
			scaleToNeedles()
            createPlot()

        },
        setZoom: _setZoom,
		setPosition: _setPosition,
        setAAPosition: function(aa_position, stop_callback, animate)
        {
            var converted_position = posToX(-aa_position) * scale
            _setPosition(converted_position, stop_callback)
            refresh(animate)
        },
        setSize: function(width, height)
        {
            config.width = width
            config.height = height

            _adjustPlotDimensions()

            _rescalePlot()

            // refresh zoom and position with current values
            _setZoomAndMove(scale, position, true)
        }
    }

    return publicSpace
}
