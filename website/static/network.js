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
    // data variables
    var kinases
    var sites
    var kinases_grouped
    var kinase_groups
    var protein

    // visualisation variables
    var nodes
    var svg
    var vis
    var force

    var zooom

    var edges = []
    var orbits

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
        var name = protein.name
        if(!protein.is_preferred)
        {
            name += '\n(' + protein.refseq + ')'
        }

        return {
            name: name,
            r: radius,
            x: (config.width - radius) / 2,
            y: (config.height - radius) / 2,
            color: 'blue',
            fixed: true
        }
    }

    var config = {
        // Required
        element: null, // specifies where network will be embedded
        data: null, // json-serialized network definition

        // Dimensions
        width: 600,
        height: null,
        ratio: 1,   // the aspect ratio
        responsive: true,  /* if responsive is set, (width, height and ratio) does not count:
        the dimensions will be adjusted to fit `element` boundaries */

        // Configuration
        show_sites: true,
        clone_by_site: true,

        // Element sizes
        site_size_unit: 5,
        minimalRadius: 6,   // of a single node

        // Callbacks
        nodeURL: (function(node) {
            return window.location.href + '#' + node.protein.refseq
        }),

        // Zoom
        minZoom: 0.5,   // allow to zoom-out up to two times
        maxZoom: 2  // allow to zoom-in up to two times
    }

    function configure(new_config)
    {
        // Automatical configuration update:
        update_object(config, new_config)

        // Manual configuration patching:
        config.height = config.height || config.width * config.ratio
    }

    function getKinasesByName(names, kinases_set)
    {
        kinases_set = kinases_set ? kinases_set : kinases

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

    function removeEdge(source, target, weight)
    {
        return edges.pop(
            {
                source: source,
                target: target,
                weight: weight
            }
        )
    }

    function prepareSites(raw_sites, index_shift)
    {
        // If kinase occurs both in a group and bounds to
        // the central protein, duplicate it's node. How?
        // 1. duplicate the data
        // 2. make the notion in the data and just add two cicrcles
        // And currently it is implemented by data duplication

        sites = []
        var cloned_kinases = []

        for(var i = 0; i < raw_sites.length; i++)
        {
            var site = raw_sites[i]

            site.name = site.position + ' ' + site.residue
            site.size = Math.max(site.name.length, 6) * config.site_size_unit
            // the site visualised as a square has bounding radius of outscribed circle on that square
            site.r = Math.sqrt(site.size * site.size / 4)
            site.node_type = 'site'
            site.node_id = i + index_shift

            // this property will be populated for kinases belonging to group in prepareKinaseGroups
            site.group = undefined

            // make links to the central protein's node from this site
            addEdge(site.node_id, 0)

            sites.push(site)

            var site_kinases = getKinasesByName(site.kinases, kinases) // TODO: also add groups here
            for(var j = 0; j < site_kinases.length; j++)
            {
                var kinase = site_kinases[j]
                if(config.clone_by_site)
                {
                    if(kinase.used)
                    {
                        kinase = clone(kinase)
                        kinase.node_id = raw_sites.length + cloned_kinases.length + index_shift
                        cloned_kinases.push(kinase)
                    }
                    else
                        kinase.used = true
                }
                addEdge(site.node_id, kinase.node_id)
            }
        }
        return cloned_kinases
    }

    function prepareKinases(all_kinases, index_shift)
    {
        // If kinase occurs both in a group and bounds to
        // the central protein, duplicate it's node. How?
        // 1. duplicate the data
        // 2. make the notion in the data and just add two cicrcles
        // And currently it is implemented by data duplication

        kinases = []
        kinases_grouped = []

        var kinases_in_groups = getKinasesInGroups()

        for(var i = 0; i < all_kinases.length; i++)
        {
            var kinase = all_kinases[i]

            kinase.r = calculateRadius(
                kinase.protein ? kinase.protein.mutations_count : 0
            )
            kinase.node_id = i + index_shift

            // this property will be populated for kinases belonging to group in prepareKinaseGroups
            kinase.group = undefined

            if(protein.kinases.indexOf(kinase.name) !== -1)
            {
                // add a kinase that binds to the central protein to `kinases` list
                kinase = clone(kinase)
                kinase.node_id = kinases.length + index_shift
                kinases.push(kinase)

                if(!config.show_sites)
                {
                    // make links to the central protein's node from those
                    // kinases that bound to the central protein (i.e.
                    // exclude those which are shown only in groups)
                    addEdge(kinase.node_id, 0)
                }
            }
            //
            if(kinases_in_groups.indexOf(kinase.name) !== -1)
            {
                // add a kinase that binds to group to `kinases_grouped` list
                kinase = clone(kinase)
                kinase.collapsed = true
                kinase.node_id = kinases_grouped.length + index_shift
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
            if(!config.show_sites)
            {
                // 0 is (by convention) the index of the central protein
                addEdge(group_index, 0)
            }
        }
    }

    function linkDistance(edge)
    {
        /*
        // make links between the core protein and groups longer,
        // so the groups stand out and do not collide with kinases
        if(edge.source.is_group)   // source node is a group
        {
            return 175
        }
        else
        */
        // let's place them in layers around the central protein
        if(edge.target.index === 0)
        {
            return orbits.getRadiusByNode(edge.source)
        }
        // dynamically adjust the length of a link between
        // a kinase located in a group and its group's node
        if(edge.target.is_group)    // target node is a group
        {
            return edge.target.expanded ? edge.target.r + edge.source.r : 0
        }
        return 100
    }

    function switchGroupState(node, state, time)
    {
        time = (time === undefined) ? 600 : time
        node.expanded = (state === undefined) ? !node.expanded : state

        function inGroup(d)
        {
            return node.index === d.group
        }

        function fadeInOut(selection)
        {
            selection
                .transition().ease('linear').duration(time)
                .attr('opacity', node.expanded ? 1 : 0)
        }

        d3.selectAll('.node')
            .filter(inGroup)
            .each(function(d){ d.collapsed = !node.expanded } )

        d3.selectAll('circle')
            .filter(inGroup)
            .transition().ease('linear').duration(time)
            .attr('r', function(d){return node.expanded ? d.r : 0})

        d3.selectAll('.label')
            .filter(inGroup)
            .call(fadeInOut)

        d3.selectAll('.link')
            .filter(function(e) { return inGroup(e.source) } )
            .call(fadeInOut)

    }

    function zoomAndMove()
    {
        vis.attr('transform', 'translate(' + d3.event.translate + ')scale(' + d3.event.scale + ')')
    }

    function focusOn(node, radius)
    {
        area = radius * 2 * 1.2

        var scale = Math.min(config.width / area, config.height / area)
        var translate = [config.width / 2 - node.x * scale, config.height / 2 - node.y * scale]

        svg.transition()
            .duration(750)
            .call(zoom.translate(translate).scale(scale).event)
    }

    function charge(node)
    {
        // we could disable charge for collapsed nodes completly and instead
        // stick these nodes to theirs groups, but this might be inefficient
        return node.collapsed ? -1 : -100
    }

    function nodeClick(node)
    {
        if(d3.event.defaultPrevented === false)
        {
            if(node.is_group)
            {
                switchGroupState(node)
                force.start()
            }
            else
            {
                window.location.href = config.nodeURL(node)
            }
        }
    }

    function nodeHover(node, hover_in)
    {
        nodes
            .filter(function(d){ return d.name === node.name })
            .classed('hover', hover_in)
    }

    function resize()
    {
        if(config.responsive)
        {
            var dimensions = svg.node().getBoundingClientRect()
            config.width = dimensions.width
            config.height = dimensions.height
            config.ratio = dimensions.height / dimensions.width
        }
        svg.attr('viewBox', '0 0 ' + config.width + ' ' + config.height)
    }

    var publicSpace = {
        init: function(user_config)
        {
            configure(user_config)

            zoom = d3.behavior.zoom()
                .scaleExtent([config.minZoom, config.maxZoom])
                .on('zoom', zoomAndMove)

            svg = d3.select(config.element).append('svg')
                .attr('preserveAspectRatio', 'xMinYMin meet')
                .attr('class', 'svg-content-responsive')
                .call(zoom)

            resize()

            vis = svg.append('g')

            var data = config.data

            kinase_groups = data.kinase_groups
            protein = data.protein

            var protein_node = createProteinNode()
            var nodes_data = [protein_node]

            prepareKinases(data.kinases, nodes_data.length)
            Array.prototype.push.apply(nodes_data, kinases)
            Array.prototype.push.apply(nodes_data, kinases_grouped)

            prepareKinaseGroups(nodes_data.length)
            Array.prototype.push.apply(nodes_data, kinase_groups)

            var elements = kinases.concat(kinase_groups)

            if(config.show_sites)
            {
                cloned_kinases = prepareSites(data.sites, nodes_data.length)
                Array.prototype.push.apply(nodes_data, sites)
                Array.prototype.push.apply(nodes_data, cloned_kinases)
                elements = sites
            }

            orbits = Orbits()
            orbits.init(elements, protein_node)
            orbits.placeNodes()

            for(var j = 0; j < kinases_grouped.length; j++)
            {
                // force positions of group members to be equal
                // to initial positions of central node in the group
                var kinase = kinases_grouped[j]
                var group = nodes_data[kinase.group]

                kinase.x = group.x
                kinase.y = group.y
            }

            force = d3.layout.force()
                .gravity(0.05)
                .distance(100)
                .charge(charge)
                .size([config.width, config.height])
                .nodes(nodes_data)
                .links(edges)
                .linkDistance(linkDistance)
                // notes for future: it is possible to speed up the force with:
                // .on('start', start) and using `requestAnimationFrame` in start()
                // but this creates a terrible effect of laggy animation

            var links = vis.selectAll('.link')
                .data(edges)
                .enter().append('line')
                .attr('class', 'link')
                .style('stroke-width', function(d) { return Math.sqrt(d.weight) })

            nodes = vis.selectAll('.node')
                .data(nodes_data)
                .enter().append('g')
                .attr('class', 'node')
                .call(force.drag)
                .on('click', nodeClick)
                .on('mouseover', function(d){ nodeHover(d, true) })
                .on('mouseout', function(d){ nodeHover(d, false) })
                // cancel other events (like pining the background)
                // to allow nodes movement (by force.drag)
                .on("mousedown", function(d) { d3.event.stopPropagation() })


            var kinase_nodes = nodes
                .filter(function(d){ return d.node_type !== 'site' })

            kinase_nodes
                .append('circle')
                .attr('r', function(d){ return d.r })
                .attr('stroke', function(node) {
                    var default_color = '#905590'
                    return node.color || default_color
                })

            var site_nodes = nodes
                .filter(function(d){ return d.node_type === 'site' })
                .append('g')
                .attr('transform', function(d){ return 'translate(' + [-d.size / 2, -d.size / 2] + ')'} )

            site_nodes
                .append('rect')
                .attr('width', function(d){ return d.size + 'px' })
                .attr('height', function(d){ return d.size + 'px' })

            kinase_nodes
                .append('text')
                .attr('class', 'label')

            site_nodes
                .append('text')
                .attr('class', 'label')

            var labels = nodes.selectAll('.label')
                .text(function(d){ return d.name })
                .style('font-size', function(d) {
                    if(d.node_type === 'site')
                        return '7px'
                    else
                        return fitTextIntoCircle(d, this) + 'px'
                })

            site_nodes.selectAll('.label')
                .attr('dy', '1.5em')
                .attr('dx', function(d) {
                    return d.size/ 2 + 'px'
                })

            site_nodes
                .append('text')
                .text(function(d) { return d.nearby_sequence })
                .style('font-size', function(d) {
                    return '5.5px'
                })
                .attr('dy', '3.8em')
                .attr('dx', function(d) {
                    return d.size/ 2 + 'px'
                })

            var group_nodes = nodes
                .filter(function(d){ return d.is_group })

            group_nodes
                .append('text')
                .attr('class', 'type')
                .text(function(d){ return 'family ' + d.kinases.length  + '/' + d.total_cnt })
                .style('font-size', function(d) {
                    return fitTextIntoCircle(d, this) * 0.5 + 'px'
                })
                .attr('dy', function(d) {
                    return fitTextIntoCircle(d, this) * 0.35 + 'px'
                })


            force.on('tick', function(e) {
                force
                    .linkDistance(linkDistance)
                    .charge(charge)

                links
                    .attr('x1', function(d) { return d.source.x })
                    .attr('y1', function(d) { return d.source.y })
                    .attr('x2', function(d) { return d.target.x })
                    .attr('y2', function(d) { return d.target.y })

                nodes.attr('transform', function(d){ return 'translate(' + [d.x, d.y] + ')'} )

            })

            focusOn(protein_node, orbits.getMaximalRadius())

            force.start()

            for(var i = 0; i < kinase_groups.length; i++)
            {
                // collapse the group immediately (time=0)
                switchGroupState(kinase_groups[i], false, 0)
            }

            $(window).on('resize', resize)
        }
    }

    return publicSpace
}())
