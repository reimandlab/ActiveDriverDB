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

var Network = function ()
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

    var zoom

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

        var pos = zoom.viewport_to_canvas([(config.width - radius) / 2, (config.height - radius) / 2]);

        return {
            type: types.central,
            name: name,
            r: radius,
            x: pos[0],
            y: pos[1],
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
        min_zoom: 1/3.5,   // allow to zoom-out up to three and half times
        max_zoom: 3  // allow to zoom-in up to three times
    }

    function configure(new_config, callback)
    {
        // Automatic configuration update:
        update_object(config, new_config);

        get_remote_if_needed(config, 'data', callback)
    }

    function getKinasesByName(names, kinases_set)
    {
        kinases_set = kinases_set ? kinases_set : kinases

        var matching_kinases = []

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

    /*
    function getKinaseByName(name)
    {
        return getKinasesByName([name])[0]
    }
    */

    function getKinasesInGroups()
    {
        var names = []
        for(var i = 0; i < kinase_groups.length; i++)
        {
            var group = kinase_groups[i]
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

    function prepareSites(raw_sites, index_shift)
    {
        // If kinase occurs both in a group and bounds to
        // the central protein, duplicate it's node. How?
        // 1. duplicate the data
        // 2. make the notion in the data and just add two circles
        // And currently it is implemented by data duplication

        sites = []
        var cloned_kinases = []

        for(var i = 0; i < raw_sites.length; i++)
        {
            var site = raw_sites[i]

            site.name = site.position + ' ' + site.residue
            site.size = Math.max(site.name.length, 6) * config.site_size_unit
            // the site visualised as a square has bounding radius of outscribed circle on that square
            site.size += site.mutations_count / 2
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
        // 2. make the notion in the data and just add two circles
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
        for(var i = 0; i < kinase_groups.length; i++)
        {
            var group = kinase_groups[i]

            group.type = types.group
            group.node_id = i + index_shift

            var pos = zoom.viewport_to_canvas([config.width, config.height]);
            group.x = Math.random() * pos[0]
            group.y = Math.random() * pos[1]

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
            if(!config.show_sites)
            {
                // 0 is (by convention) the index of the central protein
                addEdge(group_index, 0)
            }
        }
    }

    function linkDistance(edge)
    {
        // if a node wants to overwrite other behaviours, let him
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

        nodes
            .filter(inGroup)
            .each(function(d){ d.collapsed = !node.expanded } )

        nodes.selectAll('circle')
            .filter(inGroup)
            .transition().ease('linear').duration(time)
            .attr('r', function(d){return node.expanded ? d.r : 0})

        nodes.selectAll('.name')
            .filter(inGroup)
            .call(fadeInOut)

        links
            .filter(function(e) { return inGroup(e.source) } )
            .call(fadeInOut)

    }

    function focusOn(node, radius, animation_speed)
    {
        var area = radius * 2
        zoom.center_on([node.x, node.y], area, animation_speed)
    }

    function charge(node)
    {
        // we could disable charge for collapsed nodes completely and instead
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
                if(node.exposed)
                {
                    // move node back to the orbit
                    node.exposed = false
                    node.link_distance = config.default_link_distance
                    publicSpace.zoom_fit()
                }
                else
                {
                    // let's expose the node
                    node.exposed = true
                    var shift = get_max_radius() * 3
                    node.x = central_node.x + shift
                    node.y = central_node.y
                    node.link_distance = shift
                    focusOn(
                        {x: node.x, y: node.y},
                        shift / 2.5
                    )
                }
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
            var dimensions = $(svg.node()).parent().get(0).getBoundingClientRect()
            config.width = dimensions.width
            config.height = dimensions.height
            config.ratio = dimensions.height / dimensions.width
        }
        else {
            config.height = config.height || config.width * config.ratio
        }
        zoom.set_viewport_size(config.width, config.height)
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

        kinases.concat(kinase_groups)

        if(config.show_sites)
        {
            var cloned_kinases = prepareSites(data.sites, nodes_data.length)
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

                var tg_alpha = site.y / site.x
                var alpha = Math.atan(tg_alpha)

                // give 1/2 of angle space per interactor
                var angles_per_actor = Math.PI / 180

                // set starting angle for first interactor
                var angle = alpha - (site.interactors.length - 1) / 2 * angles_per_actor

                for(var k = 0; k < site.interactors.length; k++)
                {
                    var x = Math.cos(angle) * link_distance
                    var y = Math.sin(angle) * link_distance
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


    function get_max_radius()
    {
        var radius = orbits.getMaximalRadius()
        if(config.show_sites)
            radius += config.default_link_distance
        return radius
    }

    function init()
    {
        svg = prepareSVG(config.element)

        zoom = Zoom()
        zoom.init({
            element: svg,
            min: config.min_zoom,
            max: config.max_zoom,
            viewport: svg.node().parentNode,
            on_move: function(event) { dispatch.networkmove(event) }
        })


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
                .size(zoom.viewport_to_canvas([config.width, config.height]))
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


            var tooltip = Tooltip()
            tooltip.init({
                id: 'node',
                template: function(node){
                    return nunjucks.render(
                        'node_tooltip.njk',
                        {
                            node: node,
                            types: types,
                            nodeURL: config.nodeURL
                        }
                    )
                },
                viewport: svg.node().parentElement
            })

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
                .filter(function(d){ return d.type == types.kinase })

            var group_nodes = nodes
                .filter(function(d){ return d.type == types.group })

            var central_nodes = nodes
                .filter(function(d){ return d.type == types.central })

            var kinases_color_scale = create_color_scale(
                [
                    0,
                    d3.max(kinases, function(d){
                        return d.protein ? d.protein.mutations_count : 0
                    }) || 0
                ],
                ['#ffffff', '#007FFF']
            )

            //var sites_color_scale = create_color_scale(
            //    [0, central_node.protein.mutations_count],
            //    ['#ffffff', '#ff0000']
            //)

            kinase_nodes
                .append('circle')
                .attr('r', function(d){ return d.r })
                .attr('class', 'kinase protein-like shape')

            var octagon_cr_to_a_ratio = 1 / (Math.sqrt(4 + 2 * Math.sqrt(2)) / 2)
            var octagon_angle = (180 - 135) * (2 * Math.PI) / 360

            group_nodes
                .append('polygon')
                .attr('points', function(d){
                    var points = []
                    // d.r is a circumradius here
                    var a = d.r * octagon_cr_to_a_ratio
                    var x = -d.r + 1
                    var y = d.r / 2
                    //points.push([x, y])
                    for(var i = 0; i < 8; i++)
                    {
                        var angle = octagon_angle * (i + 1)
                        x += a * Math.sin(angle)
                        y += a * Math.cos(angle)
                        points.push([x, y])
                    }
                    return points
                })
                .attr('class', 'group shape')

            central_nodes
                .append('ellipse')
                .attr('rx', function(d){ return d.r })
                .attr('ry', function(d){ return d.r / 5 * 4 })
                .attr('class', 'central protein-like shape')

            nodes.selectAll('.protein-like')
                .attr('fill', function(d){
                    if(d.protein)
                        return kinases_color_scale(d.protein.mutations_count)
                })

            var site_nodes = nodes
                .filter(function(d){ return d.type === types.site })

            site_nodes
                .attr('class', function(d){
                    return 'node ' + d.impact
                })
                .append('rect')
                .attr('width', function(d){ return d.size + 'px' })
                .attr('height', function(d){ return d.size + 'px' })
                //.attr('fill', function(d){
                //    return sites_color_scale(d.mutations_count)
                //})
                .attr('class', 'site shape')
                .attr('transform', function(d){ return 'translate(' + [-d.size / 2, -d.size / 2] + ')'} )

            nodes
                .append('text')
                .attr('class', 'name')
                .text(function(d){
                    if(d.name.length > 9)
                        return d.name.substring(0, 7) + '...'
                    return d.name
                })
                .style('font-size', function(d) {
                    if(d.type !== types.site)
                        return fitTextIntoCircle(d, this) + 'px'
                })

            site_nodes.selectAll('.name')
                .style('font-size', '8px')
                .attr('dy', '-0.5em')

            site_nodes
                .append('text')
                .text(function(d) { return d.nearby_sequence })
                .style('font-size', '5.5px')
                .attr('dy', '1.5em')

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

            function kinase_site_with_loss(d)
            {
                return (
                    d.source.type == types.kinase &&
                    d.target.type == types.site &&
                    d.target.mimp_losses.indexOf(d.source.name) != -1
                )
            }

            links
                .filter(kinase_site_with_loss)
                .classed('loss-prediction', true)
                // the link will be scaled linearly to the number of mimp loss
                // predictions. This number will be always >= 1 (because we
                // are working on such filtered subset of links)
                .style('stroke-width', function(d){
                    var count = 0
                    for(var i = 0; i < d.target.mimp_losses.length; i++)
                        count += (d.target.mimp_losses[i] == d.source.name)
                    return count * 1.5
                })

            for(var i = 0; i < kinase_groups.length; i++)
            {
                // collapse the group immediately (time=0)
                switchGroupState(kinase_groups[i], false, 0)
            }

            $(window).on('resize', resize)

            config.onload()
    }

    var publicSpace = {
        init: function(user_config)
        {
            if(!user_config)
            {
                init()
            }
            else
            {
                configure(user_config, publicSpace.init)
            }

        },
        zoom_in: function(){
            zoom.set_zoom(zoom.get_zoom() * 1.25)
        },
        zoom_out: function(){
            zoom.set_zoom(zoom.get_zoom() / 1.25)
        },
        zoom_fit: function(animation_speed){
            var radius = get_max_radius()
            focusOn(central_node, radius, animation_speed)
        },
        destroy: function()
        {
            svg.remove()
        }
    }

    return publicSpace
}