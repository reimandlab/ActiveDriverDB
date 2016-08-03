var NeedlePlot = function ()
{
    var svg, zoom, vis, vertical_scalable, unit
    var scale = 1
	var position = 0

    var colorMap = {
      'missense': 'yellow',
      'synonymous': 'lightblue',
      'truncating': 'red',
      'splice-site': 'orange',
      'other': 'grey'
    }

    var config = {
        animations_speed: 200,
        // 90 is width of description
        paddings: {bottom: 30, top: 0, left: 89, right: 1},
        y_scale: 'auto',
        sequenceLength: null,
        element: null,
        mutations: null,
        sites: null,
        colorMap: colorMap,
        legends: {x: 'Sequence', y: '# of mutations'},
        width: 600,
        height: null,
        zoom_callback: null,
        position_callback: null,
        ratio: 0.5,
        min_zoom: 1,
        max_zoom: 10
    }

	function get_remote_if_needed(new_config, name)
	{
        if(typeof new_config[name] == 'string')
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

    function configure(new_config)
    {
		allowed_remote_data = ['mutations', 'sites']

		for(var i = 0; i < allowed_remote_data.length; i++)
		{
			name = allowed_remote_data[i]
			get_remote_if_needed(new_config, name)
		}

        // Automatical configuration update:
        update_object(config, new_config)

        // Manual configuration patching:
        config.height = config.height || config.width * config.ratio

    }

    function makeNeedles()
    {
		console.log(config.mutations)
        var mutations = config.mutations
        var needles = []
        for(var i = 0; i < mutations.length; i++)
        {
			// TODO
        }
		if (config.y_scale == 'auto')
		{
			// TODO
			config.y_scale = 5
		}
        return needles
    }

    function createPlot()
    {
		unit = (config.width - config.paddings.left - config.paddings.right) / config.sequenceLength

		var padding = 35

        zoom = d3.behavior.zoom()
            .scaleExtent([config.min_zoom, config.max_zoom])
            .on('zoom', zoomAndMove)


        svg = d3.select(config.element).append('svg')
            .attr('preserveAspectRatio', 'xMinYMin meet')
            .attr('viewBox', '0 0 ' + config.width + ' ' + config.height)
            .attr('class', 'svg-content-responsive')
            .call(zoom)

		paddings = svg.append('g')
			.attr('class', 'paddings')
			.attr('transform', 'translate(' + config.paddings.left + ' , 0)')

		vertical_scalable = paddings.append('g')
			.attr('class', 'vertical scalable')

        var leftPadding = paddings.append('rect')
            .attr('fill', 'white')
            .attr('width', config.paddings.left)
            .attr('height', config.height)
			.attr('transform', 'translate(-' + config.paddings.left + ' , 0)')

        var yScale = d3.scale.linear()
            .domain([0, config.y_scale])
            .range([config.height - config.paddings.bottom, padding])

        var yAxis = d3.svg.axis()
			.tickFormat(d3.format('d'))
            .orient('left')
            .scale(yScale)

        var yAxisGroup = paddings.append('g')
			.attr('class', 'y axis')
            .call(yAxis)

		domain = [0, config.sequenceLength]

        xScale = d3.scale.linear()
            .domain(domain)
            .range([0, config.width - config.paddings.left - config.paddings.right])

        xAxis = d3.svg.axis()
            .orient('bottom')
            .scale(xScale)

		var bottom_axis_pos = config.height - config.paddings.bottom

        var xAxisGroup = paddings.append('g')
			.attr('class', 'x axis')
			.attr('transform', 'translate(0, ' + bottom_axis_pos + ')')
            .call(xAxis)

        vis = vertical_scalable.append('g')

		var site_height = 10

        var sites = vis.selectAll('.site')
            .data(config.sites)
            .enter()
            .append('g')
            .attr('transform', function(d){ return 'translate(' + [posToX(d.start), bottom_axis_pos - site_height] + ')' })
            .attr('class', 'site')

        var site_boxes = sites
			.append('rect')
			.attr('width', function(d){ return d.end - d.start})
			.attr('height', site_height)

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
        domain = [start, start + axis_coverage]
		xScale.domain(domain)
		canvas.select('.x.axis').call(xAxis)
    }

    function refresh(animate)
    {
        adjustXAxis(animate)
        adjustContent(animate)
    }

    function zoomAndMove()
    {
		_setZoom(d3.event.scale)
		_setPosition(d3.event.translate[0])

        refresh()
    }


	function _setZoom(new_scale, stop_callback)
	{
        if(scale == new_scale)
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
			needles = makeNeedles()
            createPlot()

			if(config.legends.x)
			{
				paddings.append('text')
					.attr('class', 'label')
					.text(config.legends.x)
					.attr('x', config.width / 2)
					.attr('y', config.height - config.paddings.bottom)
					.attr('dy','2.4em')
					.style('text-anchor','middle')
			}

			if(config.legends.y)
			{
				paddings.append('text')
					.attr('class', 'label')
					.text(config.legends.y)
					.style('text-anchor','middle')
					.attr('transform','translate(' + -40 + ' ' + config.height / 2 + ') rotate(-90)')
			}

        },
        setZoom: _setZoom,
		setPosition: _setPosition,
        setAAPosition: function(aa_position, stop_callback, animate)
        {
            var converted_position = posToX(-aa_position) * scale
            _setPosition(converted_position, stop_callback)
            refresh(animate)
        }
    }

    return publicSpace
}
