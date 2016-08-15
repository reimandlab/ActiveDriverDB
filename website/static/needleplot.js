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
        site_height: 10,
        animations_speed: 200,
        // 90 is width of description
        paddings: {bottom: 30, top: 30, left: 89, right: 1},
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
          'network-rewiring': 'lightblue',
          'direct': 'red',
          'proximal': 'orange',
          'other': 'grey'
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
            max = 0
            muts = config.mutations
            for(var i = 0; i < muts.length; i++)
            {
                max = Math.max(max, muts[i].value)
            }
			config.y_scale = max * 5 / 4
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
            .range([config.height - config.paddings.top, config.paddings.bottom])

        var height_unit = (config.height - config.paddings.bottom - config.paddings.top) / config.y_scale

        axes.y.obj.scale(axes.y.scale)
        axes.y.group.call(axes.y.obj)

		var bottom_axis_pos = config.height - config.paddings.bottom

        axes.x.obj.scale(axes.x.scale)
        axes.x.group
	        .attr('transform', 'translate(0, ' + bottom_axis_pos + ')')
            .call(axes.x.obj)

        sites
            .attr('transform', function(d)
                {
                    return 'translate(' + [posToX(d.start), bottom_axis_pos - config.site_height] + ')'
                }
            )

        site_boxes
			.attr('width', function(d){ return posToX(d.end - d.start) })

        needles
            .attr('transform', function(d)
                {
                    return 'translate(' + [posToX(d.coord), bottom_axis_pos] + ')'
                }
            )

        needles.selectAll('line')
            .attr('stroke-width', posToX(1) / 2 + 'px')
            .attr('y1', function(d){ return -d.value * height_unit + 'px' })

        needles.selectAll('circle')
            .attr('r', posToX(1) / 2 + 'px')
            .attr('y', function(d){ return -d.value * height_unit + 'px' })

        leftPadding.attr('height', config.height)

        if(legend.x.obj)
            legend.x.obj.attr('x', config.width / 2)
        if(legend.y.obj)
            legend.y.obj.attr('transform','translate(' + -40 + ' ' + config.height / 2 + ') rotate(-90)')
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

        axes.y.scale = d3.scale.linear()
            .domain([0, config.y_scale])

        axes.y.obj = d3.svg.axis()
            .orient('left')
            .scale(axes.y.scale)
            // TODO
			.tickFormat(d3.format('d'))
            .tickSubdivide(0)

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

        needles = vis.selectAll('.needle')
            .data(config.mutations)
            .enter()
            .append('g')
            .attr('class', 'needle')

        needles
            .append('line')
                .attr('x1', 0)
                .attr('x2', 0)
                .attr('y2', 0)

        needles
            .append('circle')
                .attr('fill', function(d)
                    {
                        return config.color_map[d.category]
                    }
                )
                .attr('x', '0')

        sites = vis.selectAll('.site')
            .data(config.sites)
            .enter()
            .append('g')
            .attr('class', 'site')

        site_boxes = sites
			.append('rect')
			.attr('height', config.site_height)

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
        var canvas = canvasAnimated(animate)
		canvas.select('.vertical.scalable').attr('transform', 'translate(' + position + ', 0)scale(' + scale + ', 1)')
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
