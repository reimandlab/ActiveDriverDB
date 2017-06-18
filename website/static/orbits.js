var Orbits = function ()
{
    var nodes = null
    var central_node = null

    var by_node = {}
    var orbits = []

    var config = {
        order_by: 'r',  // new of data attribute to be used in placing nodes in orbits. The node with highest value of this attribute will be used to populate first place on the first orbit, then the next in order to populate second and so on until the orbit will be filled completely. Then the same will be applied to the second orbit and so on. Radius is the best choice in means of optimal place use, but if all nodes have the same radius it might be better idea to use sorting to encode something else.
        stroke: 2.2,
        spacing: 15, // the distance between orbits
        first_ring_scale: 1.5 // `first_ring_scale * central_node.radius` define radius of the first ring
    }

    function configure(new_config)
    {
        if(!new_config) return

        // Automatical configuration update:
        update_object(config, new_config)
    }

    function perimeter(R)
    {
        return 2 * Math.PI * R
    }

    function compareNodes(a, b)
    {
        if (a[config.order_by] < b[config.order_by])
          return -1
        if (a[config.order_by] > b[config.order_by])
            return 1
          return 0
    }

    // warning: using constructor pattern, not module
    function Orbit(number, initial_outer_radius)
    {
        this.number = number
        this.nodes_count = 0

        this.outer_radius = initial_outer_radius
        this.radius = null  // inner radius in pixels
        this.width = 0   // how much space takes the biggest node on this orbit / 2

        this.space_available = perimeter(this.outer_radius)    // space available on outer belt

        this.addNode = function(node)
        {
            by_node[node.name] = this.number
            this.nodes_count += 1
        }

        this.setDimensions = function(outer_radius)
        {
            this.radius = outer_radius - this.width
        }

        this.getSpaceRequiredForNewNode = function()
        {
            var angle = 2 * Math.asin(this.width / this.outer_radius)
            return this.outer_radius * angle
        }

        this.recalculateSpace = function(old_perimeter)
        {
            var percent_available = this.space_available / old_perimeter
            this.space_available = perimeter(this.outer_radius) * percent_available
        }
    }

    function newOrbit(initial_outer_radius)
    {
        var orbit = new Orbit(orbits.length, initial_outer_radius)
        orbits.push(orbit)
        return orbit
    }

    function calculateOrbits()
    {
        // radius of the first orbit, depends of the size of central protein
        var base_length = central_node.r * config.first_ring_scale

        var orbit = newOrbit(base_length)

        for(var i = 0; i < nodes.length; i++)
        {
            var node = nodes[i]
            var node_width = node.r + config.stroke

            if(node_width > orbit.width)
            {
                // recalculate width, radius & available space
                var old_perimeter = perimeter(orbit.outer_radius)

                // the outer belt will be larger - let's rescale the outer belt
                orbit.width = node_width
                orbit.outer_radius = base_length + orbit.width * 2
                orbit.recalculateSpace(old_perimeter)

            }
            var space_for_node = orbit.getSpaceRequiredForNewNode()
            // if it does not fit, lets move the next orbit, reset values
            if(orbit.space_available < space_for_node)
            {
                // save the orbit which is full
                orbit.setDimensions(orbit.outer_radius)

                // create new orbit
                base_length = orbit.outer_radius + config.spacing

                // move to the new orbit
                orbit = newOrbit(base_length + node_width * 2)
                orbit.width = node_width
                space_for_node = orbit.getSpaceRequiredForNewNode()
            }

            // finaly since it has to fit to the orbit right now, place it on the current orbit
            orbit.addNode(node)
            orbit.space_available -= space_for_node

            // (orbit.space_available >= 0) should always be true

        }
        orbit.setDimensions(orbit.outer_radius)
    }

    function getSlots()
    {
        // how many nodes should be placed on each of the available orbits
        var slots = new Array(orbits.length)
        for(var i = 0; i < orbits.length; i++)
            slots[i] = orbits[i].nodes_count
        return slots
    }

    var publicSpace = {
        init: function(orbiting_nodes, the_central_node, config)
        {
            nodes = orbiting_nodes
            central_node = the_central_node
            configure(config)
            // sort nodes by radius from the smallest
            nodes.sort(compareNodes)
            calculateOrbits()
        },
        getRadiusByNode: function(node)
        {
            return orbits[by_node[node.name]].radius
        },
        getOrbit: function(node)
        {
            return orbits[by_node[node.name]]
        },
        getMaximalRadius: function()
        {
            var orbit = orbits[orbits.length - 1]
            return orbit.radius + orbit.width
        },
        placeNodes: function()
        {
            var slots = getSlots()

            for(var i = 0; i < nodes.length; i++)
            {
                var node = nodes[i]

                var orbit_id = by_node[node.name]
                var orbit = orbits[orbit_id]

                var full_circle = Math.PI * 2

                var fraction_occupied = slots[orbit_id] / orbit.nodes_count
                var angle = full_circle * fraction_occupied

                node.x = orbit.radius * Math.cos(angle) + central_node.x
                node.y = orbit.radius * Math.sin(angle) + central_node.y

                slots[orbit_id] -= 1
            }
        }
    }

    return publicSpace

}
