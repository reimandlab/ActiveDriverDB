var Orbits = (function ()
{
    var nodes = null
    var central_node = null

    var by_node = {}
    var orbits = []
    
    var config = {
        stroke: 2.2,
        spacing: 5, // the distance between orbits
        first_ring_scale: 1.5 // `first_ring_scale * central_node.radius` define radius of the first ring
    }

    function configure(new_config)
    {
        if(!new_config) return

        // Automatical configuration update:
        for(var key in new_config)
        {
            if(new_config.hasOwnProperty(key))
            {
                config[key] = new_config[key]
            }
        }
    }

    function perimeter(R)
    {
        return 2 * Math.PI * R
    }

    function compareRadius(a, b)
    {
        if (a.r < b.r)
          return -1
        if (a.r > b.r)
            return 1
          return 0
    }

    // warning: using constructor pattern, not module
    function Orbit(number)
    {
        this.number = number
        this.nodes_count = 0

        this.radius = null
        this.width = null   // how much space takes the biggest node on this orbit

        this.addNode = function(node)
        {
            by_node[node.name] = this.number
            this.nodes_count += 1
        }

        this.setDimensions = function(R, length_extend)
        {
            this.radius = R - length_extend
            this.width = length_extend
        }
    }

    function calculateOrbits()
    {
        // radius of the first orbit, depends of the size of central protein
        var base_length = central_node.r * config.first_ring_scale

        orbits.push(new Orbit(0))
        var length_extend = 0  // how much the radius will extend on the current orbit

        var R = base_length + length_extend * 2
        var outer_belt_perimeter = perimeter(R)
        var available_space_on_outer_belt = outer_belt_perimeter

        for(var i = 0; i < nodes.length; i++)
        {
            var node = nodes[i]

            if(node.r > length_extend)
            {
                // the outer belt will be larger - let's rescale the outer belt
                length_extend = node.r + config.stroke
                R = base_length + length_extend * 2

                var new_outer_belt_perimeter = perimeter(R)
                percent_available = available_space_on_outer_belt / outer_belt_perimeter
                available_space_on_outer_belt = new_outer_belt_perimeter * percent_available
                outer_belt_perimeter = new_outer_belt_perimeter

            }
            var angle = 2 * Math.asin(length_extend / R)
            var l = R * angle
            // if it does not fit, lets move the next orbit, reset values
            if(available_space_on_outer_belt < l)
            {
                // save the orbit which is full
                orbits[orbits.length - 1].setDimensions(R, length_extend)
                // create new orbit
                base_length = R + length_extend + config.spacing
                R = base_length + length_extend * 2
                outer_belt_perimeter = perimeter(R)
                available_space_on_outer_belt = outer_belt_perimeter
                length_extend = node.r + config.stroke
                angle = 2 * Math.asin(length_extend / R)
                l = R * angle
                // move to the new orbit
                orbits.push(new Orbit(orbits.length))
            }

            // finaly since it has to fit to the orbit right now, place it on the current orbit
            orbits[orbits.length - 1].addNode(node)
            available_space_on_outer_belt -= l
            if(available_space_on_outer_belt < 0) available_space_on_outer_belt = 0

        }
        orbits[orbits.length - 1].setDimensions(R, length_extend)
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
            nodes.sort(compareRadius)
            calculateOrbits()
        },
        getRadiusByNode: function(node)
        {
            return orbits[by_node[node.name]].radius
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

} ())
