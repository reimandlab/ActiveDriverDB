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
    var central_node

    // visualisation variables
    var nodes
    var svg
    var vis
    var force
    var links

    var zooom

    var edges = []
    var orbits

    var dispatch = d3.dispatch('networkmove')

    var types = {
        kinase: new String('Kinase'),
        group: new String('Family or group'),
        site: new String('Site'),
        central: new String('Analysed protein')
    }

    function fitTextIntoCircle(d, context)
    {
        var radius = d.r
        return Math.min(2 * radius, (2 * radius - 8) / context.getComputedTextLength() * 24)
    }

    function calculateRadius()
    {
        return config.radius
    }

    function createProteinNode(protein)
    {
        var radius = calculateRadius()
        var name = protein.name
        if(!protein.is_preferred)
        {
            name += '\n(' + protein.refseq + ')'
        }

        return {
            type: types.central,
            name: name,
            r: radius,
            x: (config.width - radius) / 2,
            y: (config.height - radius) / 2,
            color: 'blue',
            fixed: true,
            protein: protein
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
        default_link_distance: 100,
        site_kinase_link_weight: 1.3,

        // Element sizes
        site_size_unit: 5,
        radius: 6,   // of a single node

        // Callbacks
        nodeURL: (function(node) {
            return window.location.href + '#' + node.protein.refseq
        }),

        // Zoom
        min_zoom: 1/7,   // allow to zoom-out up to seven times
        max_zoom: 2  // allow to zoom-in up to two times
    }

    function configure(new_config)
    {
        // Automatical configuration update:
        update_object(config, new_config)
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
            site.type = types.site
            site.node_id = i + index_shift

            // this property will be populated for kinases belonging to group in prepareKinaseGroups
            site.group = undefined

            // make links to the central protein's node from this site
            addEdge(site.node_id, 0)

            sites.push(site)

            var site_kinases = getKinasesByName(site.kinases, kinases)
            site_kinases = site_kinases.concat(getKinasesByName(site.kinase_groups, kinase_groups))

            site.interactors = []

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
                addEdge(kinase.node_id, site.node_id, config.site_kinase_link_weight)
                site.interactors.push(kinase)
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

            kinase.type = types.kinase
            kinase.r = calculateRadius()
            kinase.node_id = i + index_shift

            // this property will be populated for kinases belonging to group in prepareKinaseGroups
            kinase.group = undefined

            if(central_node.protein.kinases.indexOf(kinase.name) !== -1)
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

            group.type = types.group
            group.node_id = i + index_shift

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

            group.r = calculateRadius()
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
        // if a node wnats to overwrite other bahaviours, let him
        if(edge.source.link_distance)
        {
            return edge.source.link_distance
        }
        // let's place them in layers around the central protein
        if(edge.target.index === 0)
        {
            return orbits.getRadiusByNode(edge.source)
        }
        // dynamically adjust the length of a link between
        // a kinase located in a group and its group's node
        if(edge.target.type === types.group)    // target node is a group
        {
            return edge.target.expanded ? edge.target.r + edge.source.r : 0
        }
        return config.default_link_distance / edge.weight
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
        dispatch.networkmove(this)
    }

    function focusOn(node, radius, animation_speed)
    {
        animation_speed = (typeof animation_speed === 'undefined') ? 750 : animation_speed

        area = radius * 2 * 1.2

        var scale = Math.min(config.width / area, config.height / area)
        var translate = [config.width / 2 - node.x * scale, config.height / 2 - node.y * scale]

        svg.transition()
            .duration(animation_speed)
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
            if(node.type === types.group)
            {
                switchGroupState(node)
                force.start()
            }
            else if(node.type === types.site)
            {
                var shift = orbits.getMaximalRadius() * 3
                node.x = central_node.x + shift
                node.y = central_node.y
                node.link_distance = shift
                force.start()
            }
        }
    }

    function nodeHover(node, hover_in)
    {
        if(node.type === types.site)
        {
            nodes
                .filter(function(d){ return node.interactors.indexOf(d) !== -1 })
                .classed('hover', hover_in)
        }
        else
        {
            nodes
                .filter(function(d){ return d.name === node.name })
                .classed('hover', hover_in)
        }
    }

    function forceTick(e)
    {
        force
            .linkDistance(linkDistance)
            .charge(charge)

        links
            .attr('x1', function(d) { return d.source.x })
            .attr('y1', function(d) { return d.source.y })
            .attr('x2', function(d) { return d.target.x })
            .attr('y2', function(d) { return d.target.y })

        nodes.attr('transform', function(d){ return 'translate(' + [d.x, d.y] + ')'} )

        dispatch.networkmove(this)
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
        else {
            config.height = config.height || config.width * config.ratio
        }
        svg.attr('viewBox', '0 0 ' + config.width + ' ' + config.height)
    }

    function set_zoom(new_scale)
    {
        var old_scale = zoom.scale()
        zoom.scale(new_scale)

        // if we exceed limits, new_scale as provided won't be the same as the real, set scale, so here it is measured again
        new_scale = zoom.scale()

        var translate = zoom.translate()
        var factor = (old_scale - new_scale)

        zoom.translate(
            [
                translate[0] + factor * config.width / 2 ,
                translate[1] + factor * config.height / 2
            ]
        )

        vis.transition().ease('linear').duration(150)
            .attr('transform', 'translate(' + zoom.translate() + ')scale(' + zoom.scale() + ')')
    }

    function createNodes(data)
    {

        kinase_groups = data.kinase_groups

        central_node = createProteinNode(data.protein)
        var nodes_data = [central_node]

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
        }

        return nodes_data
    }


    function placeNodes(nodes_data)
    {
        var orbiting_nodes
        orbits = Orbits()

        if(config.show_sites)
            orbiting_nodes = sites
        else
            orbiting_nodes = kinases.concat(kinase_groups)


        orbits.init(orbiting_nodes, central_node, {
            spacing: 95,
            order_by: config.show_sites ? 'kinases_count' : 'r'
        })
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

        if(config.show_sites)
        {
            var link_distance = config.default_link_distance / config.site_kinase_link_weight

            for(var i = 0; i < sites.length; i++)
            {
                var site = sites[i]
                if(!site.x)
                    site.x = 0.0001

                tg_alpha = site.y / site.x
                alpha = Math.atan(tg_alpha)

                // give 1/2 of angle space per interactor
                var angles_per_actor = 1 * Math.PI / 180

                // set starting angle for first interactor
                var angle = alpha - (site.interactors.length - 1) / 2 * angles_per_actor

                for(var k = 0; k < site.interactors.length; k++)
                {
                    x = Math.cos(angle) * link_distance
                    y = Math.sin(angle) * link_distance
                    var interactor = site.interactors[k]
                    interactor.x = site.x + x
                    interactor.y = site.y + y
                    angle += angles_per_actor
                }
            }
        }
    }

    function create_color_scale(domain, range)
    {
        return d3.scale
            .linear()
            .domain(domain)
            .interpolate(d3.interpolateRgb)
            .range(range)
    }


    var publicSpace = {
        init: function(user_config)
        {
            configure(user_config)

            zoom = prepareZoom(config.min_zoom, config.max_zoom, zoomAndMove)

            svg = prepareSVG(config.element)
                .call(zoom)

            // we don't want to close tooltips after panning (which is set to emit
            // stopPropagation on start what allows us to detect end-of-panning events)
            svg.on('click', function(){
                if(d3.event.defaultPrevented) d3.event.stopPropagation()
            })

            resize()

            vis = svg.append('g')

            var nodes_data = createNodes(config.data)

            placeNodes(nodes_data)

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

            links = vis.selectAll('.link')
                .data(edges)
                .enter().append('line')
                .attr('class', 'link')
                .style('stroke', function(d) {
                    if(d.source.type == types.kinase && d.source.mimp_gain)
                        return 'red'
                })
                .style('stroke-width', function(d) {
                    if(d.source.type == types.kinase && d.source.mimp_gain)
                        return 2 + Math.sqrt(d.weight)
                    return Math.sqrt(d.weight)
                })

            var tooltip = Tooltip()
            tooltip.init(
                function(node){
                    return nunjucks.render(
                        'node_tooltip.njk',
                        {
                            node: node,
                            types: types,
                            nodeURL: config.nodeURL
                        }
                    )
                },
                'node',
                svg.node()
            )

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
                .on('mousedown', function(d) { d3.event.stopPropagation() })
                .call(tooltip.bind)

            dispatch.on('networkmove', function(){
                tooltip.moveToElement()
            })


            var kinase_nodes = nodes
                .filter(function(d){ return d.type !== types.site })

            var kinases_color_scale = create_color_scale(
                [
                    0,
                    d3.max(kinases, function(d){
                        return d.protein ? d.protein.mutations_count : 0
                    }) || 0
                ],
                ['#ffffff', '#ff0000']
            )

            var sites_color_scale = create_color_scale(
                [0, central_node.protein.mutations_count],
                ['#ffffff', '#ff0000']
            )

            kinase_nodes
                .append('circle')
                .attr('r', function(d){ return d.r })
                .attr('stroke', function(node) {
                    var default_color = '#905590'
                    return node.color || default_color
                })
                .attr('fill', function(d){
                    if(d.protein)
                        return kinases_color_scale(d.protein.mutations_count)
                    else
                        return 'lightblue'
                })

            var site_nodes = nodes
                .filter(function(d){ return d.type === types.site })
                .append('g')
                .attr('transform', function(d){ return 'translate(' + [-d.size / 2, -d.size / 2] + ')'} )

            site_nodes
                .append('rect')
                .attr('width', function(d){ return d.size + 'px' })
                .attr('height', function(d){ return d.size + 'px' })
                .attr('fill', function(d){
                    return sites_color_scale(d.mutations_count)
                })

            kinase_nodes
                .append('text')
                .attr('class', 'label')

            site_nodes
                .append('text')
                .attr('class', 'label')

            var labels = nodes.selectAll('.label')
                .text(function(d){
                    if(d.name.length > 6)
                    {
                        var name = d.name.substring(0, 7)
                        return name + '...'
                    }
                    return d.name
                })
                .style('font-size', function(d) {
                    if(d.type === types.site)
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
                .filter(function(d){ return d.type === types.group })

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


            force.on('tick', forceTick)

            publicSpace.zoom_fit(0)    // grasp everything without animation (avoids repeating zoom lags if they occur)

            force.start()

            for(var i = 0; i < kinase_groups.length; i++)
            {
                // collapse the group immediately (time=0)
                switchGroupState(kinase_groups[i], false, 0)
            }

            $(window).on('resize', resize)
        },
        zoom_in: function(){
            set_zoom(zoom.scale() * 1.25)
        },
        zoom_out: function(){
            set_zoom(zoom.scale() / 1.25)
        },
        zoom_fit: function(animation_speed){
            var radius = orbits.getMaximalRadius()
            if(config.show_sites)
                radius += config.default_link_distance
            focusOn(central_node, radius, animation_speed)
        }
    }

    return publicSpace
}())
