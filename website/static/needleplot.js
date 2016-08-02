var NeedlePlot = function ()
{
    var svg, zoom, vis, vertical_scalable, unit

    var colorMap = {
      'missense': 'yellow',
      'synonymous': 'lightblue',
      'truncating': 'red',
      'splice-site': 'orange',
      'other': 'grey'
    }

    var config = {
        animations_speed: 300,
        // 90 is width of description
        paddings: {bottom: 0, top: 0, left: 90, right: 1},
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

        config.legends = config.legens || {
          x: config.name + ' Amino Acid sequence (' + config.refseq + ')',
          y: '# of mutations in ' + config.name
        }

    }

    function zoomAndMove()
    {
		_setZoom(d3.event.scale)
        //vertical_scalable.attr('transform', 'translate(' + [0, 0] + ')scale(' + d3.event.scale + ', 1)')
    }

    function makeNeedles()
    {
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

	function posToX(pos)
	{
		return pos * unit
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

		var paddings = svg.append('g')
			.attr('class', 'paddings')
			.attr('transform', 'translate(' + config.paddings.left + ' , 0)')

        var yScale = d3.scale.linear()
            .domain([0, config.y_scale])
            .range([config.height - padding, padding])

        var yAxis = d3.svg.axis()
			.tickFormat(d3.format('d'))
            .orient('left')
            .scale(yScale)

        var yAxisGroup = paddings.append('g')
			.attr('class', 'y axis')
            .call(yAxis)

        xScale = d3.scale.linear()
            .domain([0, config.sequenceLength])
            .range([0, config.width - config.paddings.left - config.paddings.right])

        xAxis = d3.svg.axis()
            .orient('bottom')
            .scale(xScale)

		vertical_scalable = paddings.append('g')
			.attr('class', 'vertical scalable')

		var bottom_axis_pos = config.height - padding

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

	function _setZoom(scale, trigger_callback)
	{

		xScale.domain([0, config.sequenceLength / scale])
		t = svg
			.transition().ease('quad').duration(config.animations_speed)
		t.select('.x.axis').call(xAxis)

		t.select('.vertical.scalable').attr('transform', 'scale(' + scale + ', 1)')

        if(trigger_callback !== false && config.zoom_callback)
        {
            config.zoom_callback(scale, false)
        }
	}

    var publicSpace = {
        init: function(new_config)
        {
            configure(new_config)
			needles = makeNeedles()
            createPlot()

        },
        setZoom: _setZoom
    }

    return publicSpace
}
