function assert(condition)
{
    if(!condition)
    {
        if (typeof Error !== 'undefined')
        {
            throw new Error('Assertion failed')
        }
        throw 'Assertion failed'
    }
}

function clone(object)
{
    // this implementation won't handle functions and
    // more advanced objects - only simple key-values
    return JSON.parse(JSON.stringify(object))
}

var Network = (function ()
{
    var kinases = null
    var kinases_grouped = null
    var kinase_groups = null
    var protein = null

    var edges = []

    function fitTextIntoCircle(d, context)
    {
        var radius = d.r
        return Math.min(2 * radius, (2 * radius - 8) / context.getComputedTextLength() * 24)
    }

    function calculateRadius(mutations_count, is_group)
    {
        var r = config.minimalRadius
        // the groups are shown as 1.5 times bigger
        r *= is_group ? 1.5 : 1
        // more mutations = bigger circle
        r += 6 * Math.log10(mutations_count + 1)

        return r
    }

    function createProteinNode()
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
            return window.location.href + '#' + node.name
        })
    }

    function configure(new_config)
    {
        // Automatical configuration update:
        for(var key in new_config)
        {
            if(new_config.hasOwnProperty(key))
            {
                config[key] = new_config[key]
            }
        }
        // Manual configuration patching:
        config.height = config.height || config.width * config.ratio
    }

    function getKinasesByName(names, kinases_set)
    {
        kinases_set ? kinases_set : kinases

        matching_kinases = []

        for(var i = 0; i < kinases_set.length; i++)
        {
            for(var j = 0; j < names.length; j++)
            {
                if(kinases_set[i].name === names[j])
                {
                    matching_kinases.push(kinases_set[i])
                }
            }
        }
        return matching_kinases
    }

    function getKinaseByName(name)
    {
        return getKinasesByName([name])[0]
    }

    function getKinasesInGroups()
    {
        var names = []
        for(var i = 0; i < kinase_groups.length; i++)
        {
            group = kinase_groups[i]
            Array.prototype.push.apply(names, group.kinases)
        }
        return names
    }

    function addEdge(source, target, weight)
    {
        weight = weight || 1
        edges.push(
            {
                source: source,
                target: target,
                weight: weight
            }
        )
    }

    function prepareKinases(all_kinases)
    {
        // If kinase occurs both in a group and bounds to
        // the central protein, duplicate it's node. How?
        // 1. duplicate the data
        // 2. make the notion in the data and just add two cicrcles
        // And currently it is implemented by data duplication

        kinases = []
        kinases_grouped = []

        var kinases_in_groups = getKinasesInGroups()

        alt = window.location.hash.substr(1) // just temporary

        for(var i = 0; i < all_kinases.length; i++)
        {
            var kinase = all_kinases[i]
            kinase.x = Math.random() * config.width
            kinase.y = Math.random() * config.height
            kinase.r = calculateRadius(
                kinase.protein ? kinase.protein.mutations_count : 0
            )
            kinase.node_id = i + 1

            // this property will be populated for kinases belonging to group in prepareKinaseGroups
            kinase.group = undefined

            if(protein.kinases.indexOf(kinase.name) !== -1)
            {
                // add a kinase that binds to the central protein to `kinases` list
                if(!alt)
                {
                    kinase = clone(kinase)
                }
                kinase.node_id = kinases.length + 1
                kinases.push(kinase)

                // make links to the central protein's node from those
                // kinases that bound to the central protein (i.e.
                // exclude those which are shown only in groups)
                addEdge(kinase.node_id, 0)
            }
            // 
            if(kinases_in_groups.indexOf(kinase.name) !== -1)
            {
                // add a kinase that binds to group to `kinases_grouped` list
                if(!alt)
                {
                    kinase = clone(kinase)
                }
                kinase.node_id = kinases_grouped.length + 1
                kinases_grouped.push(kinase)
            }
        }
    }

    function prepareKinaseGroups(index_shift)
    {
        var kinases_in_groups = getKinasesInGroups()
        for(var i = 0; i < kinase_groups.length; i++)
        {
            var group = kinase_groups[i]

            group.is_group = true

            group.x = Math.random() * config.width
            group.y = Math.random() * config.height

            var group_kinases = getKinasesByName(group.kinases, kinases_grouped)
            assert(group_kinases.length <= group.kinases.length)
            var group_index = index_shift + i

            var mutations_in_kinases = 0
            for(var j = 0; j < group_kinases.length; j++)
            {
                var kinase = group_kinases[j]
                kinase.group = group_index

                mutations_in_kinases += kinase.protein ? kinase.protein.mutations_count : 0
                assert(kinase.node_id + kinases.length < group_index)
                addEdge(kinase.node_id + kinases.length, group_index)
            }

            group.r = calculateRadius(
                mutations_in_kinases / group_kinases.length || 0,
                true
            )
            group.color = 'red'
            // 0 is (by convention) the index of the central protein
            addEdge(group_index, 0)
        }
    }

    function linkDistance(edge)
    {
        // make links between the core protein and groups longer,
        // so the groups stand out and do not colide with kinases
        if(edge.source.is_group)   // source node is a group
        {
            return 175
        }
        // adjust the length of a link between a kinase located in
        // a group and its group's node
        if(edge.target.is_group)    // target node is a group
        {
            return edge.target.expanded ? edge.target.r + edge.source.r : 0
        }
        return 100
    }

    function switchGroupState(node, state)
    {
        node.expanded = (state === undefined) ? !node.expanded : state

        function inGroup(d)
        {
            return node.index === d.group
        }

        function fadeInOut(selection)
        {
            selection
                .transition().ease('linear').duration(600)
                .attr('opacity', node.expanded ? 1 : 0)
        }

        d3.selectAll('circle')
            .filter(inGroup)
            .transition().ease('linear').duration(600)
            .attr('r', function(d){return node.expanded ? d.r : 0})

        d3.selectAll('.label')
            .filter(inGroup)
            .call(fadeInOut)

         d3.selectAll('.link')
            .filter(function(e) { return inGroup(e.source) } )
            .call(fadeInOut)
    }

    function startsVisible(node)
    {
        // whether a node should start visible or not
        // nodes belonging to groups should be hidden on start
        return (node.group === undefined) ? 1 : 0
    }

    var publicSpace = {
        init: function(user_config)
        {
            configure(user_config)

            var vis = d3.select(config.element).append('svg')
                .attr('preserveAspectRatio', 'xMinYMin meet')
                .attr('viewBox', '0 0 ' + config.width + ' ' + config.height)
                .classed('svg-content-responsive', true)

            var data = config.data

            kinase_groups = data.kinase_groups
            protein = data.protein

            var protein_node = createProteinNode()
            var nodes_data = [protein_node]

            prepareKinases(data.kinases)
            Array.prototype.push.apply(nodes_data, kinases)
            Array.prototype.push.apply(nodes_data, kinases_grouped)

            prepareKinaseGroups(nodes_data.length)
            Array.prototype.push.apply(nodes_data, kinase_groups)

            var force = d3.layout.force()
                .gravity(0.05)
                .distance(100)
                .charge(-100)
                .size([config.width, config.height])
                .nodes(nodes_data)
                .links(edges)
                .linkDistance(linkDistance)
                .start()

            var links = vis.selectAll(".link")
                .data(edges)
                .enter().append("line")
                .attr("class", "link")
                .attr('opacity', function(e){ return startsVisible(e.source) } )
                .style("stroke-width", function(d) { return Math.sqrt(d.weight) })

            var nodes = vis.selectAll('.node') 
                .data(nodes_data)
                .enter().append('g')
                .attr('transform', function(d){ return 'translate(' + [d.x, d.y] + ')' })
                .attr('class', 'node')
                .call(force.drag)
                .on('click', function(node) {
                    if(d3.event.defaultPrevented === false)
                    {
                        if(node.is_group)
                        {
                            switchGroupState(node)
                        }
                        else
                        {
                            window.location.href = config.nodeURL(node)
                        }
                    }
                })

            var circles = nodes.append('circle')
                .attr('r', function(d){ return startsVisible(d) ? d.r : 0})
                .attr('stroke', function(node) {
                    var default_color = '#905590'
                    return node.color || default_color
                }) 

            var labels = nodes.append('text')
                .attr('class', 'label')
                .text(function(d){ return d.name })
                .style('font-size', function(d) { return fitTextIntoCircle(d, this) + 'px' })
                .attr('opacity', startsVisible)

            nodes
                .filter(function(d){ return d.is_group })
                .append('text')
                .attr('class', 'type')
                .text(function(d){ return 'family' + '(' + d.kinases.length  + ')' })
                .style('font-size', function(d) { return fitTextIntoCircle(d, this) * 0.5 + 'px' })
                .attr('dy', function(d) { return fitTextIntoCircle(d, this) * 0.35 + 'px' })


            force.on('tick', function() {

                links
                    .attr("x1", function(d) { return d.source.x })
                    .attr("y1", function(d) { return d.source.y })
                    .attr("x2", function(d) { return d.target.x })
                    .attr("y2", function(d) { return d.target.y })

                nodes.attr('transform', function(d){ return 'translate(' + [d.x, d.y] + ')'} )

                force
                    .linkDistance(linkDistance)
                    .start()
                })
        }
    }

    return publicSpace
}())
