function append(destination, new_content)
{
    Array.prototype.push.apply(destination, new_content)
}

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
    var sites
    var groups
    var central_node
    var force_manager

    // visualisation variables
    var nodes
    var svg
    var vis
    var links

    var zoom

    var edges = []
    var orbits

    var dispatch = d3.dispatch('networkmove')

    var types = {
        kinase: new String('Kinase'),
        drug: new String('Drug'),
        group: new String('Family or group'),
        site: new String('Site'),
        central: new String('Analysed protein')
    }

    var tooltip

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
        site_kinase_link_weight: 1.15,
        collide_drugs: true,

        // Element sizes
        site_size_unit: 5,
        radius: 6,   // of a single node

        // Callbacks
        nodeURL: (function(node) {
            return window.location.href + '#' + node.protein.refseq
        }),

        // Zoom
        min_zoom: 1/4,   // allow to zoom-out up to four times
        max_zoom: 3  // allow to zoom-in up to three times
    }

    function configure(new_config, callback)
    {
        // Automatic configuration update:
        update_object(config, new_config);

        get_remote_if_needed(config, 'data', callback)
    }

    function select_kinases_by_name(names, kinases)
    {
        var all_matching_kinases = [];

        for(var i = 0; i < names.length; i++)
        {
            var name = names[i];
            var matching_kinases = kinases.filter(function(kinase) {return kinase.name === name});
            append(all_matching_kinases, matching_kinases);
        }
        return all_matching_kinases
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

    function prepareSites(sites, standalone_kinases)
    {
        var cloned_kinases = []

        function parse(site)
        {
            site.visible_interactors = 0

            site.name = site.position + ' ' + site.residue
            site.size = Math.max(site.name.length, 6) * config.site_size_unit
            // the site visualised as a square has bounding radius of outscribed circle on that square
            site.size += site.mutations_count / 2
            site.r = Math.sqrt(site.size * site.size / 4)
            site.type = types.site
            site.collisions_active = true

            // this property will be populated for kinases belonging to group in prepareKinaseGroups
            site.group = undefined

            // make links to the central protein's node from this site
            addEdge(site, central_node)

            var site_kinases = select_kinases_by_name(site.kinases, standalone_kinases);
            append(site_kinases, select_kinases_by_name(site.kinase_groups, groups));

            site.interactors = [];

            function associate_kinase_with_site(kinase_template)
            {
                var kinase;
                if(config.clone_by_site)
                {
                    if(kinase_template.used)
                    {
                        kinase = clone(kinase_template);
                        cloned_kinases.push(kinase)
                    }
                    else {
                        kinase_template.used = true
                        kinase = kinase_template
                    }
                }
                else {
                    kinase = kinase_template
                }
                addEdge(kinase, site, config.site_kinase_link_weight);
                site.interactors.push(kinase);
                site.visible_interactors += 1
            }
            site_kinases.forEach(associate_kinase_with_site);
        }

        sites.forEach(parse);

        return cloned_kinases
    }

    function prepareKinases(all_kinases)
    {
        // If kinase occurs both in a group and bounds to
        // the central protein, duplicate it's node. How?
        // 1. duplicate the data
        // 2. make the notion in the data and just add two circles
        // And currently it is implemented by data duplication

        var kinases = []

        for(var i = 0; i < all_kinases.length; i++)
        {
            var kinase = all_kinases[i]

            kinase.type = types.kinase
            kinase.collisions_active = false
            kinase.r = calculateRadius()

            // this property will be populated for kinases belonging to group in prepareKinaseGroups
            kinase.group = undefined
            // will be populated if and when sites created
            kinase.site = undefined

            if(central_node.protein.kinases.indexOf(kinase.name) !== -1)
            {
                // add a kinase that binds to the central protein to `kinases` list
                kinase = clone(kinase)
                kinases.push(kinase)

                if(!config.show_sites)
                {
                    // make links to the central protein's node from those
                    // kinases that bound to the central protein (i.e.
                    // exclude those which are shown only in groups)
                    addEdge(kinase, central_node)
                }
            }
        }
        return kinases
    }

    function prepareKinaseGroups(groups, all_kinases)
    {
        var cloned_kinases = [];

        function parse(group)
        {
            group.kinases_names = group.kinases;
            group.type = types.group;
            group.drugs = [];   // No drugs for kinase groups are displayed currently

            function is_in_group(kinase)
            {
                return group.kinases_names.indexOf(kinase.name) !== -1
            }

            var group_kinases = all_kinases.filter(is_in_group);
            var mutations_in_kinases = 0;

            function associate_kinase_with_group(kinase_template)
            {
                var kinase = clone(kinase_template);
                cloned_kinases.push(kinase);

                kinase.group = group;
                mutations_in_kinases += kinase.protein ? kinase.protein.mutations_count : 0;
                addEdge(kinase, group);
            }

            group_kinases.forEach(associate_kinase_with_group);

            group.r = calculateRadius();

            if(!config.show_sites)
                addEdge(group, central_node)
        }

        groups.forEach(parse);

        return cloned_kinases;
    }

    function linkDistance(edge)
    {
        // if a node wants to overwrite other behaviours, let him
        if(edge.source.link_distance)
        {
            return edge.source.link_distance
        }
        // let's place sites (or kinases when show sites = false) in layers around the central protein
        if(edge.target.index === 0)
        {
            return orbits.getRadiusByNode(edge.source)
        }
        // dynamically adjust the length of a link between
        // a kinase located in a group and its group's node
        if(edge.target.type === types.group)    // target node is a group
        {
            if(edge.target.expanded)
            {
                return edge.target.r + edge.source.r
            }
            return 0
        }
        return config.default_link_distance / edge.weight
    }

    function ForceManager(config)
    {
        var force_affected_nodes = [];
        var force_affected_links = [];
        var force;

        force = d3.layout.force()
            .friction(0.5)
            .gravity(0)
            .distance(100)
            .charge(charge)
            .size(config.size)
            .linkDistance(linkDistance);

        var publicSpace = {
            drag: force.drag,
            charge: force.charge,
            start: force.start,
            stop: force.stop,
            on: force.on,
            hide_nodes_links: function(node)
            {
                var to_remove = [];
                for(var e = 0; e < force_affected_links.length; e++)
                {
                    var edge = force_affected_links[e];
                    // noinspection EqualityComparisonWithCoercionJS
                    if(edge.source == node)
                        to_remove.push(edge)
                }

                for(var r = 0; r < to_remove.length; r++)
                {
                    var index = force_affected_links.indexOf(to_remove[r]);
                    force_affected_links.splice(index, 1);
                }
                node._removed_links = to_remove;
            },
            restore_nodes_links: function(node)
            {
                if(node._removed_links)
                {
                    for(var e = 0; e < node._removed_links.length; e++)
                    {
                        force_affected_links.push(node._removed_links[e])
                    }
                }

            },
            hide_from_force: function(node)
            {
                var index = force_affected_nodes.indexOf(node);
                if(index !== -1)
                    force_affected_nodes.splice(index, 1)
            },
            make_visible_for_force: function(node)
            {
                force_affected_nodes.push(node)
            },
            settle_force: function(n)
            {
                force.start();
                for (var i = n; i > 0; --i) force.tick()
                force.stop();
            },
            update_force_affected_nodes: function(nodes_data, links_data)
            {
                if(nodes_data)
                    append(force_affected_nodes, nodes_data);
                if(links_data)
                    append(force_affected_links, links_data);

                force.nodes(force_affected_nodes);
                force.links(force_affected_links);
            }
        }

        return publicSpace;
    }

    function create_versor(x, y)
    {
        var length = Math.sqrt(Math.pow(x, 2) + Math.pow(y, 2))
        if(length === 0)
            return [0, 0]
        else
            return [x / length, y /length]
    }

    function switchGroupState(group, state, time)
    {
        time = (time === undefined) ? 600 : time
        group.expanded = (state === undefined) ? !group.expanded : state

        function inGroup(d)
        {
            return group === d.group
        }

        function fadeInOut(selection)
        {
            selection
                .transition().ease('linear').duration(time)
                .attr('opacity', group.expanded ? 1 : 0)
        }
        refresh_group_collisions_state(group);

        nodes
            .filter(inGroup)
            .each(function(node){
                node.collapsed = !group.expanded;
                group.visible_interactors += (node.collapsed ? -1 : +1)

                if(node.collapsed)
                {
                    node.x = group.x;
                    node.y = group.y;
                    force_manager.hide_from_force(node);
                    force_manager.hide_nodes_links(node);
                }
                else
                {
                    var center_of_interest;

                    if(group.site && group.site.exposed)
                        center_of_interest = group.site;
                    else
                        center_of_interest = central_node;

                    var versor = create_versor(center_of_interest.x - group.x, center_of_interest.y - group.y);

                    node.x = group.x - (Math.random() * 2 * node.r) * versor[0];
                    node.y = group.y - (Math.random() * 2 * node.r) * versor[1];

                    force_manager.restore_nodes_links(node);
                    force_manager.make_visible_for_force(node);
                }
            })

        var scale = group.expanded ? 1 : 0

        nodes.selectAll('.shape')
            .filter(inGroup)
            .transition().ease('linear').duration(time)
            .attr('transform', 'scale(' + scale + ')')

        nodes.selectAll('.name')
            .filter(inGroup)
            .call(fadeInOut)

        links
            .filter(function(e) { return inGroup(e.source) } )
            .call(fadeInOut)

        force_manager.update_force_affected_nodes()

    }

    function focusOn(node, radius, animation_speed)
    {
        var area = radius * 2.2
        zoom.center_on([node.x, node.y], area, animation_speed)
    }

    function charge(node)
    {
        // we could disable charge for collapsed nodes completely and instead
        // stick these nodes to theirs groups, but this might be inefficient
        // noinspection EqualityComparisonWithCoercionJS
        if(node.group){
            if(node.collapsed)
            {
                return 0
            }
            if(!node.site)
                return -10
            return -150 / node.group.site.visible_interactors
        }
        // noinspection EqualityComparisonWithCoercionJS
        // noinspection EqualityComparisonWithCoercionJS
        if((node.type == types.kinase || node.type == types.drug || node.type == types.group) && !(node.site && node.site.exposed)){
            if(!node.site)
                return -10
            return -150 / node.site.visible_interactors
        }
        return 0
    }

    function refresh_group_collisions_state(group) {
        if(!config.show_sites) return
        var site = group.site
        for (var j = 0; j < group.kinases.length; j++) {
            var kinase = group.kinases[j]
            kinase.collisions_active = group.expanded && site.exposed
        }
    }

    function is_site_protein_edge(site)
    {
        return function(edge){ return edge.source === site }
    }

    function stop_exposing_site(site)
    {
        // move node back to the orbit
        site.exposed = false
        site.link_distance = site.previous_link_distance
        force_manager.charge(charge)
        force_manager.start()

        var link = links.filter(is_site_protein_edge(site)).transition().duration(3000)
        link.attr('class', 'link')

        tooltip.unstick()
        tooltip.hide()
        tooltip.ignore_next_signal()
    }

    function expose_site(site, camera_speed)
    {
        var link = links.filter(is_site_protein_edge(site)).transition().duration(3000)

        // let's expose the node
        site.exposed = true
        var shift = get_max_radius() * 1.5

        var max_distance_squared = 0
        for(var i = 0; i < site.interactors.length; i++)
        {
            var interactor = site.interactors[i]
            var distance_squared = Math.pow(site.x - interactor.x, 2) + Math.pow(site.y - interactor.y, 2)
            if(distance_squared > max_distance_squared)
                max_distance_squared = distance_squared
        }

        var versor = create_versor(site.x - central_node.x, site.y - central_node.y)

        // usually there is more space on sides (x axis) than below and on top as the network is displayed
        // in widescreen frame
        var screen_ratio = 1.2
        shift = shift * Math.abs(versor[0]) * screen_ratio + shift * Math.abs(versor[1]) / screen_ratio

        var dest = [central_node.x + shift * versor[0], central_node.y + shift * versor[1]]

        site.previous_link_distance = site.link_distance

        site.link_distance = shift
        site.x = dest[0]
        site.y = dest[1]

        // tooltips are annoying when popping up during camera movement
        // (those are showing up just because mouse cursor hovers over many nodes when camera is moving)
        tooltip.active(false);
        focusOn(
            {x: dest[0], y: dest[1]},
            Math.sqrt(max_distance_squared) * 1.15,
            camera_speed
        );
        setTimeout(function(){tooltip.active(true)}, camera_speed);

        force_manager.start()

        tooltip.unstick()
        tooltip.hide()
        tooltip.ignore_next_signal()

        link.attr('class', 'link link-dimmed')
    }

    function node_dbl_click(node)
    {

        if(d3.event.defaultPrevented === false)
        {
            if(node.type === types.group)
            {
                switchGroupState(node)
                tooltip.unstick()
                tooltip.hide()
                force_manager.start()
            }
            else if(node.type === types.site)
            {
                node.fixed = false

                var site = node
                var camera_speed = 2500

                if(site.exposed) // site will be de-exposed
                {
                    var return_camera_speed = camera_speed / 5;
                    stop_exposing_site(site);

                    tooltip.active(false);
                    publicSpace.zoom_fit(return_camera_speed);
                    setTimeout(function(){tooltip.active(true)}, return_camera_speed);
                }
                else // site will be exposed
                {
                    for(var s = 0; s < sites.length; s++)
                    {
                        var tested_site = sites[s]
                        if(tested_site.exposed)
                        {
                            stop_exposing_site(tested_site)
                        }
                    }

                    expose_site(site, camera_speed)

                    force_manager.charge(0)

                }
                for(var i = 0; i < site.interactors.length; i++)
                {
                    var interactor = site.interactors[i]
                    interactor.fixed = false
                    interactor.collisions_active = site.exposed
                    // noinspection EqualityComparisonWithCoercionJS
                    if(interactor.type == types.group)
                    {
                        refresh_group_collisions_state(interactor);
                    }
                    for(var d = 0; d < interactor.drugs.length; d++)
                    {
                        interactor.drugs[d].fixed = false
                    }
                }
            }
            force_manager.on('tick', create_ticker())
        }
    }

    function node_click(node)
    {
        if(d3.event.shiftKey && node !== central_node)
        {
            node.fixed = false
            tooltip.ignore_next_signal()
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

    function collide(node_1, node_2, min_dist, min_dist_pow)
    {
        var x = node_1.x - node_2.x
        var y = node_1.y - node_2.y

        var distance = Math.pow(x, 2) + Math.pow(y, 2)
        if(distance < min_dist_pow)
        {
            var l = Math.sqrt(distance)
            var change = (min_dist - l) / 2
            // rescale: to versor and then to displacement
            if(l)
            {
                x /= l
                x *= change
                y /= l
                y *= change
            }
            else {
                x = min_dist / 2
                y = min_dist / 2
            }
            node_1.x += x
            node_1.y += y
            node_2.x -= x
            node_2.y -= y
        }

    }

    function collide_nodes(nodes, padding, constant_radius)
    {
        nodes = nodes.data()
        if(constant_radius)
        {
            var min_dist = 2 * constant_radius + padding
            var min_dist_squared = Math.pow(min_dist, 2)

            function collide_node(node)
            {
                for(var i = 0; i < nodes.length; i++)
                {
                    var other_node = nodes[i]
                    if(node != other_node)
                    {
                        collide(node, other_node, min_dist, min_dist_squared)
                    }
                }
            }
        }
        else
        {
            function collide_node(node)
            {
                for(var i = 0; i < nodes.length; i++)
                {
                    var other_node = nodes[i]
                    if(node != other_node)
                    {
                        var min_dist = node.r + other_node.r + padding
                        collide(node, other_node, min_dist, min_dist * min_dist)
                    }
                }
            }
        }
        return collide_node
    }

    function collide_nodes_belonging_to_exposed_sites(exposed_sites, padding)
    {
        // all nodes have the same radius
        var r = config.radius
        var d = 2 * r + padding
        var d2 = Math.pow(d, 2)


        var kinases = []
        var groups = []
        exposed_sites.each(function(site){
            var interactors = site.interactors;
            append(kinases, interactors);
            append(groups, interactors.filter(
                function(node){ // noinspection EqualityComparisonWithCoercionJS
                    return node.type == types.group && node.expanded }
            ))
        })

        for(var g = 0; g < groups.length; g++)
        {
            var group = groups[g];
            append(kinases, group.kinases);
        }

        kinases = kinases.filter(function(kinase){ return kinase.collisions_active })


        function collide_sites_nodes()
        {
            // possibly: filter out kinases from other sites (but really, we have only one site exposed at time)
            for(var i = 0; i < kinases.length; i++)
            {
                var kinase_one = kinases[i]

                for(var j = i + 1; j < kinases.length; j++)
                {
                    var kinase_two = kinases[j]

                    collide(kinase_one, kinase_two, d, d2)
                }
            }
        }
        return collide_sites_nodes
    }

    function create_ticker()
    {
        var site_nodes = nodes.filter(is_of_type(types.site));
        var drug_nodes = nodes.filter(is_of_type(types.drug));

        // could be done with bounding boxes instead as sites are represented as boxes
        var site_collider = collide_nodes(site_nodes, 3)
        var drugs_collider = collide_nodes(drug_nodes, 1, config.radius * 0.8)

        var exposed_sites = site_nodes.filter(function (node) { return node.exposed });
        var nodes_collider = collide_nodes_belonging_to_exposed_sites(exposed_sites, 3);

        function forceTick(e)
        {
            site_nodes.each(site_collider);
            exposed_sites.each(nodes_collider);
            if(config.collide_drugs)
                drug_nodes.each(drugs_collider);

            links
                .attr('x1', function(d) { return d.source.x })
                .attr('y1', function(d) { return d.source.y })
                .attr('x2', function(d) { return d.target.x })
                .attr('y2', function(d) { return d.target.y })

            nodes.attr('transform', function(d){ return 'translate(' + [d.x, d.y] + ')'} );

            force_manager.start()
            dispatch.networkmove(this)
        }
        return forceTick
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

    function is_of_type(type, negation)
    {
        if(negation)
            return function(node)
            {
                // noinspection EqualityComparisonWithCoercionJS
                return node.type != type
            }

        return function(node)
        {
            // noinspection EqualityComparisonWithCoercionJS
            return node.type == type
        }
    }

    function create_drug_nodes(kinase_nodes)
    {
        var drugs = []
        kinase_nodes.forEach(function(kinase) {
            var kinase_drugs = []
            kinase.drugs_targeting_kinase_gene.forEach(
                function(drug_data)
                {
                    var drug_node = {
                        name: drug_data.name,
                        r: config.radius,
                        type: types.drug,
                        group: kinase.group,
                        data: drug_data
                    }
                    addEdge(drug_node, kinase)
                    kinase_drugs.push(drug_node)
                }
            )
            kinase.drugs = kinase_drugs
            append(drugs, kinase_drugs)
        })
        return drugs
    }

    function createNodes(data)
    {
        groups = data.kinase_groups;

        central_node = createProteinNode(data.protein);
        var nodes_data = [central_node];

        // kinases which are known to interact with protein are returned (standalone)
        // those as well as other (i.e. kinases which are in families known to interact with protein)
        // are prepared to be displayed
        var standalone_kinases = prepareKinases(data.kinases);
        append(nodes_data, standalone_kinases);

        if(config.show_sites)
        {
            var cloned_kinases = prepareSites(data.sites, standalone_kinases);
            sites = data.sites;
            append(nodes_data, cloned_kinases.filter(is_of_type(types.kinase)));
            append(nodes_data, sites);
            // those which are not kinases are groups (type was not assigned yet)
            append(groups, cloned_kinases.filter(is_of_type(types.kinase, true)))
        }
        else
        {
            sites = []
        }

        var kinases_which_are_in_groups = prepareKinaseGroups(groups, data.kinases);
        append(nodes_data, groups);
        append(nodes_data, kinases_which_are_in_groups);

        var kinase_nodes = nodes_data.filter(is_of_type(types.kinase));

        groups.forEach(function(group) {
            group.kinases = []
            kinase_nodes.forEach(function(node){
                // noinspection EqualityComparisonWithCoercionJS
                if(node.group && node.group == group)
                {
                    group.kinases.push(node)
                }
            })
        })

        var drug_nodes = create_drug_nodes(kinase_nodes)
        append(nodes_data, drug_nodes);

        // not in "associate_kinase_with_site" to void circular dependencies while cloning
        sites.forEach(function(site) {
            site.interactors.forEach(function(kinase){
                kinase.site = site
            });
        });

        nodes_data.forEach(function(node, index) { node.id = index })

        return {
            all: nodes_data,
            groups: groups,
            sites: sites,
            standalone: standalone_kinases,
            kinases: kinase_nodes
        }
    }

    function place_interactors(node, interactors, angles_per_actor, link_distance) {
        var sx = central_node.x - node.x
        var sy = central_node.y - node.y

        var alpha = Math.atan2(sy, sx)

        if (interactors.length > 1)
            angles_per_actor /= interactors.length - 1

        // set starting angle for first interactor
        var angle = alpha - (interactors.length - 1) / 2 * angles_per_actor

        for (var k = 0; k < interactors.length; k++) {
            var x = Math.cos(angle) * link_distance
            var y = Math.sin(angle) * link_distance
            var interactor = interactors[k]
            interactor.x = node.x - x
            interactor.y = node.y - y
            angle += angles_per_actor
        }
    }

    function placeNodes(sites, standalone_kinases, kinases)
    {
        var orbiting_nodes
        orbits = Orbits()

        if(config.show_sites)
            orbiting_nodes = sites
        else
            orbiting_nodes = standalone_kinases.concat(groups)


        orbits.init(orbiting_nodes, central_node, {
            spacing: 95,
            order_by: config.show_sites ? 'kinases_count' : 'r'
        })
        orbits.placeNodes()

        if(config.show_sites)
        {
            var link_distance = config.default_link_distance / config.site_kinase_link_weight

            for(var i = 0; i < sites.length; i++)
            {
                var site = sites[i]

                var site_orbit = orbits.getOrbit(site)
                var angles_available_for_site = Math.PI * 2 / site_orbit.nodes_count
                place_interactors(site, site.interactors, angles_available_for_site, link_distance)
            }
        }

        var link = config.default_link_distance / config.site_kinase_link_weight
        for(var j = 0; j < kinases.length; j++)
        {
            var kinase = kinases[j]
            place_interactors(kinase, kinase.drugs, Math.PI * 2 / 360, link)
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

        vis = svg.append('g')

        zoom = Zoom()
        zoom = zoom.init({
            element: svg,
            inner_element: vis,
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

        var created_nodes = createNodes(config.data);
        var nodes_data = created_nodes.all;

        placeNodes(created_nodes.sites, created_nodes.standalone, created_nodes.kinases);

        force_manager = ForceManager({
            size: zoom.viewport_to_canvas([config.width, config.height])
        })

        force_manager.update_force_affected_nodes(nodes_data, edges)

        links = vis.selectAll('.link')
            .data(edges)
            .enter().append('line')
            .attr('class', 'link')

        tooltip = Tooltip()
        tooltip.init({
            id: 'node',
            template: function(node){
                return nunjucks.render(
                    'node_tooltip.njk',
                    {
                        refseq: central_node.protein.refseq,
                        node: node,
                        types: types,
                        nodeURL: config.nodeURL
                    }
                )
            },
            viewport: document.body,
            callback: function(element){
                $(element).find('.site-muts-table').bootstrapTable()
            }
        })

        force_manager.drag()
            .on('dragstart', function(d){
                d3.event.sourceEvent.stopPropagation()
                d.fixed = true
            })

        nodes = vis.selectAll('.node')
            .data(nodes_data)
            .enter().append('g')
            .attr('class', 'node')
            .call(force_manager.drag)
            .on('click', node_click)
            .on('dblclick', node_dbl_click)
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
            .filter(is_of_type(types.kinase));

        var group_nodes = nodes
            .filter(is_of_type(types.group));

        var central_nodes = nodes
            .filter(is_of_type(types.central));

        var drug_nodes = nodes
            .filter(is_of_type(types.drug));

        var kinases_color_scale = create_color_scale(
            [
                0,
                d3.max(created_nodes.standalone, function(d){
                    return d.protein ? d.protein.mutations_count : 0
                }) || 0
            ],
            ['#ffffff', '#007FFF']
        );

        kinase_nodes
            .append('circle')
            .attr('r', function(d){ return d.r })
            .attr('class', 'kinase protein-like shape')

        function radians(x){
            return x * Math.PI / 180
        }

        var ich_outer_angle = radians(150) // between 120 and 180
        var ich_inner_angle = radians(180) - ich_outer_angle

        function isotoxal_concave_hexagon_points(d) {
            var points = [];
            var outscribed_triangle_edge = 2 * (d.r * Math.sqrt(3) / 2)
            var edge = (outscribed_triangle_edge / 2) / Math.sin(ich_outer_angle / 2)

            var x = 0;
            var y = -d.r;

            var x_change = Math.sin(ich_inner_angle / 2) * edge
            var y_change = Math.cos(ich_inner_angle / 2) * edge

            points.push([x, y])
            x += x_change
            y += y_change
            points.push([x, y])

            var l = outscribed_triangle_edge / 2 - x_change
            x += l
            y += Math.sin((radians(180) - ich_outer_angle) / 2 + ich_inner_angle) * edge
            points.push([x, y])

            x -= y_change
            y -= x_change
            points.push([x, y])

            x -= y_change
            y += x_change
            points.push([x, y])

            x += l
            y -= Math.sin((radians(180) - ich_outer_angle) / 2 + ich_inner_angle) * edge
            points.push([x, y])

            return points
        }

        drug_nodes
            .append('polygon')
            .attr('points', isotoxal_concave_hexagon_points)
            .attr('class', 'drug shape')

        var octagon_cr_to_a_ratio = 1 / (Math.sqrt(4 + 2 * Math.sqrt(2)) / 2);
        var octagon_angle = (180 - 135) * (2 * Math.PI) / 360;

        function octagon_points(d) {
            var points = [];
            // d.r is a circumradius here
            var a = d.r * octagon_cr_to_a_ratio;
            var x = -d.r + 1;
            var y = d.r / 2;
            for(var i = 0; i < 8; i++)
            {
                var angle = octagon_angle * (i + 1);
                x += a * Math.sin(angle);
                y += a * Math.cos(angle);
                points.push([x, y])
            }
            return points
        }

        group_nodes
            .append('polygon')
            .attr('points', octagon_points)
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
            .filter(is_of_type(types.site));

        site_nodes
            .attr('class', function(d){
                return 'node ' + d.impact
            })
            .append('rect')
            .attr('width', function(d){ return d.size + 'px' })
            .attr('height', function(d){ return d.size + 'px' })
            .attr('class', 'site shape')
            .attr('transform', function(d){ return 'translate(' + [-d.size / 2, -d.size / 2] + ')'} )

        nodes
            .append('text')
            .attr('class', 'name')
            .text(function(d){
                //if(d.name.length > 9)
                //    return d.name.substring(0, 7) + '...'
                return d.name
            })
            .style('font-size', function(d) {
                if(d.type !== types.site)
                    return fitTextIntoCircle(d, this) + 'px'
            })
            .attr('y', function (d) {
                if(d.type === types.drug)
                    return d.r * 0.8
            })

        site_nodes.selectAll('.name')
            .style('font-size', '8px')
            .attr('dy', '-0.5em')

        site_nodes
            .append('text')
            .text(function(d) { return d.sequence.slice(4, -4) })
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

        publicSpace.zoom_fit(0)    // grasp everything without animation (avoids repeating zoom lags if they occur)

        force_manager.start()

        function kinase_site_with_mimp_effect(effect)
        {
            var effect_accessor = 'mimp_' + effect
            return function(d)
            {
                // noinspection EqualityComparisonWithCoercionJS
                // noinspection EqualityComparisonWithCoercionJS
                // noinspection EqualityComparisonWithCoercionJS
                var site = d.target;
                if (site.type != types.site) return false;

                var kinase = d.source

                return (
                    (
                        kinase.type == types.kinase &&
                        site[effect_accessor].indexOf(kinase.name) != -1
                    ) ||
                    (
                        kinase.type == types.group &&
                        site[effect_accessor + '_family'].indexOf(kinase.name) != -1
                    )
                )
            }
        }

        ['losses', 'gains'].forEach(
            function(effect)
            {
                var effect_accessor = 'mimp_' + effect
                links
                    .filter(kinase_site_with_mimp_effect(effect))
                    .classed(effect + '-prediction', true)
                    // the link will be scaled linearly to the number of mimp loss
                    // predictions. This number will be always >= 1 (because we
                    // are working on such filtered subset of links)
                    .style('stroke-width', function(d){
                        var kinase = d.source
                        var accessor = effect_accessor
                        if(kinase.type == types.group){
                            accessor += '_family'
                            p(kinase)
                        }
                        var site = d.target
                        var count = 0
                        var mimp = site[accessor]
                        for(var i = 0; i < mimp.length; i++)
                        { // noinspection EqualityComparisonWithCoercionJS
                            count += (mimp[i] == kinase.name)
                        }
                        return count * 1.5
                    })
            }
        )

        // collapse all groups immediately (time=0)
        groups.forEach(function(group){ switchGroupState(group, false, 0) });

        $(window).on('resize', resize)

        // fast, steady initialization
        force_manager.settle_force(10);
        var ticker = create_ticker();
        force_manager.on('tick', ticker);
        ticker();

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
            var radius = get_max_radius();
            focusOn(central_node, radius, animation_speed)
        },
        destroy: function()
        {
            svg.remove()
        }
    }

    return publicSpace
}