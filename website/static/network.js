var Network = (function ()
{
    var width = 600
    var height = 400

	function dragstarted(d) {
	  d3.event.sourceEvent.stopPropagation();
	  d3.select(this).classed('dragging', true)
	}

	function dragged(d) {
		d3.select(this).attr('transform', function(d){
			d.x += d3.event.dx
			d.y += d3.event.dy
			return 'translate(' + [d.x, d.y] + ')'
		})
	}

	function dragended(d) {
	  d3.select(this).classed('dragging', false)
	}

	function fitTextIntoCircle(d, context)
	{
		var radius = d.r
		return Math.min(2 * radius, (2 * radius - 8) / context.getComputedTextLength() * 24) + 'px';
	}

    var drag = d3.behavior.drag()
        .on('dragstart', dragstarted)
        .on('drag', dragged)
        .on('dragend', dragended)


	var publicSpace = {
		init: function(config)
		{
			config.minimalRadius = config.minimalRadius || 10

			height = width * (config.ratio || 1)

			var vis = d3.select(config.element).append('svg')
				.attr('preserveAspectRatio', 'xMinYMin meet')
				.attr('viewBox', '0 0 ' + width + ' ' + height)
				.classed('svg-content-responsive', true)

			data = config.data

			for(var i = 0; i < data['kinases'].length; i++)
			{
				var kinase = data['kinases'][i]
				kinase.x = Math.random() * width
				kinase.y = Math.random() * height

				r = config.minimalRadius
				if(kinase.protein){
					r += 6 * Math.log10(kinase.protein.mutations_count)
				}
				if(kinase.is_group)
				{
					r *= 2
				}
				kinase.r = r

			}

			var nodes = vis.selectAll('.node')
				.data(data['kinases'])
				.enter().append('g')
				.attr('transform', function(d){return 'translate(' + [d.x, d.y] + ')'})
				.attr('class', 'node')
				.call(drag)

			nodes.append('circle')
				.attr('class', 'nodes')
				.attr('r', function(kinase){ return kinase.r })
				.attr('stroke', function(kinase){
					if(kinase.is_group)
					{
						return 'green'
					}
					else
					{
						return 'red'
					}
				}) 

			nodes.append('text')
				.text(function(d){return d.name})
				.style('font-size', function(d) { return fitTextIntoCircle(d, this) })
				.attr('dy', '.35em')
		}
	}

	return publicSpace
})()
