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

    function calculateRadius(mutations_count, is_group)
    {
        is_group = is_group ? 1 : 0

        r = config.minimalRadius
        // the groups are show as two times bigger
        r *= (is_group + 1)
        // more mutations = bigger circle
        r += 6 * Math.log10(mutations_count + 1)

        return r
    }

    var config = {
        minimalRadius: 6,
        ratio: 1
    }

    function configure(new_config)
    {
        for(var key in new_config)
        {
            if(new_config.hasOwnProperty(key))
            {
                config[key] = new_config[key]
            }
        }
    }

	var publicSpace = {
		init: function(user_config)
		{
            configure(user_config)

			height = width * config.ratio

			var vis = d3.select(config.element).append('svg')
				.attr('preserveAspectRatio', 'xMinYMin meet')
				.attr('viewBox', '0 0 ' + width + ' ' + height)
				.classed('svg-content-responsive', true)

			var data = config.data

			for(var i = 0; i < data.kinases.length; i++)
			{
				var kinase = data.kinases[i]
				kinase.x = Math.random() * width
				kinase.y = Math.random() * height
                kinase.r = calculateRadius(
                    kinase.protein ? kinase.protein.mutations_count : 0,
                    kinase.is_group
                )
			}

            var nodes_data = data.kinases
            var protein = data.protein
            var protein_node =
            {
                name: protein.name,
                r: calculateRadius(protein.mutations_count),
				x: Math.random() * width,
				y: Math.random() * height
            }

            nodes_data.push(protein_node)
            console.log(nodes_data)

			var nodes = vis.selectAll('.node')
				.data(nodes_data)
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
