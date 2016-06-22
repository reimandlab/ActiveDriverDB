var Network = (function ()
{
    function fitTextIntoCircle(d, context)
    {
        var radius = d.r
        return Math.min(2 * radius, (2 * radius - 8) / context.getComputedTextLength() * 24) + 'px';
    }

    function calculateRadius(mutations_count, is_group)
    {
        var is_group = is_group ? 1 : 0

        var r = config.minimalRadius
        // the groups are shown as two times bigger
        r *= (is_group + 1)
        // more mutations = bigger circle
        r += 6 * Math.log10(mutations_count + 1)

        return r
    }

    function createProteinNode(protein)
    {
        var radius = calculateRadius(protein.mutations_count)

        return {
            name: protein.name,
            r: radius,
            x: (config.width - radius) / 2,
            y: (config.height - radius) / 2,
            color: 'blue'
        }
    }

    var config = {
        width: 600,
        height: null,
        minimalRadius: 6,   // of a single node
        ratio: 1,   // the aspect ratio of the network
        nodeURL: (function(node) {
            return window.location.hash = '#' + node.name
        })
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

            config.height = config.height || config.width * config.ratio

            var force = d3.layout.force()
                .gravity(0.05)
                .distance(100)
                .charge(-100)
                .size([config.width, config.height])


            var vis = d3.select(config.element).append('svg')
                .attr('preserveAspectRatio', 'xMinYMin meet')
                .attr('viewBox', '0 0 ' + config.width + ' ' + config.height)
                .classed('svg-content-responsive', true)

            var data = config.data

            var links = []

            for(var i = 0; i < data.kinases.length; i++)
            {
                var kinase = data.kinases[i]
                kinase.x = Math.random() * config.width
                kinase.y = Math.random() * config.height
                kinase.r = calculateRadius(
                    kinase.protein ? kinase.protein.mutations_count : 0,
                    kinase.is_group
                )
                links.push(
                    {
                        source: i,
                        target: data.kinases.length,
                        weight: 1
                    }
                )
            }

            var nodes_data = data.kinases

            var protein_node = createProteinNode(data.protein)

            nodes_data.push(protein_node)

            force
                .nodes(nodes_data)
                .links(links)
                .start()

            var link = vis.selectAll(".link")
                .data(links)
                .enter().append("line")
                .attr("class", "link")
                .style("stroke-width", function(d) { return Math.sqrt(d.weight); });

            var nodes = vis.selectAll('.node') 
                .data(nodes_data)
                .enter().append('g')
                .attr('transform', function(d){return 'translate(' + [d.x, d.y] + ')'})
                .attr('class', 'node')
                .call(force.drag)
                .on('click', function(node) {
                    if(d3.event.defaultPrevented === false)
                    {
                        window.location.href = config.nodeURL(node)
                    }
                })

            nodes.append('circle')
                .attr('class', 'nodes')
                .attr('r', function(node){ return node.r })
                .attr('stroke', function(node) {
                    var default_color = (node.is_group ? 'red' : '#905590')
                    return node.color || default_color
                }) 

            nodes.append('text')
                .text(function(d){return d.name})
                .style('font-size', function(d) { return fitTextIntoCircle(d, this) })
                .attr('dy', '.35em')
                
            force.on('tick', function() {
                link.attr("x1", function(d) { return d.source.x })
                    .attr("y1", function(d) { return d.source.y })
                    .attr("x2", function(d) { return d.target.x })
                    .attr("y2", function(d) { return d.target.y })
                    nodes.attr('transform', function(d){return 'translate(' + [d.x, d.y] + ')'})
                })

        }
    }

    return publicSpace
})()
