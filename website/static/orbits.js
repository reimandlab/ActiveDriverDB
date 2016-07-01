var Orbits = (function ()
{
    var nodes = null
    var central_node = null

    var by_node = {}
    var sizes = []
    var belt_sizes = []
    
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

    function popByRadius(nodes, min)
    {
        var r = min ? Infinity : 0
        var index = 0

        min = min ? -1 : 1

        for(var i = 0; i < nodes.length; i++)
        {
            if(min * (nodes[i].r - r) > 0)
            {
                r = nodes[i].r
                index = i
            }
        }

        return nodes.splice(index, 1)[0]
    }

    function addOrbit(R, length_extend)
    {
        sizes.push(R - length_extend)
        belt_sizes.push(length_extend)
    }

    function calculateOrbits()
    {

        var base_length = central_node.r * config.first_ring_scale   // radius of the first orbit, depends of the size of central protein

        var orbit = 0
        var length_extend = 0  // how much the radius will extend on the current orbit

        var R = base_length + length_extend * 2
        var outer_belt_perimeter = perimeter(R)
        var available_space_on_outer_belt = outer_belt_perimeter

        var len = nodes.length
        // ticker = 0
        for(var i = 0; i < len; i++)
        {
            // sort nodes by radius by picking an appropriate node
            // possible solutions: descending / ascending / biggest-smallest (greedy)

            // biggest-smallest pairs (it looks ugly, although is optimal with regard to space usage)
            // var node = ticker % 2 === 0 ? popByRadius(nodes, false) : popByRadius(nodes, true)

            // from the smallest
            var node = popByRadius(nodes, true)

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
                addOrbit(R, length_extend)
                // create new orbit
                base_length = R + length_extend + config.spacing
                R = base_length + length_extend * 2
                outer_belt_perimeter = perimeter(R)
                available_space_on_outer_belt = outer_belt_perimeter
                length_extend = node.r + config.stroke
                angle = 2 * Math.asin(length_extend / R)
                l = R * angle
                // move to the new orbit
                orbit += 1
                // ticker = 0
            }

            // finaly since it has to fit to the orbit right now, place it on the current orbit
            by_node[node.name] = orbit
            available_space_on_outer_belt -= l
            if(available_space_on_outer_belt < 0) available_space_on_outer_belt = 0

            // ticker += 1
        }
        addOrbit(R, length_extend)
    }

    function _getRadiusByNode(node)
    {
        return sizes[by_node[node.name]]
    }

    var publicSpace = {
        init: function(orbiting_nodes, the_central_node, config)
        {
            nodes = orbiting_nodes
            central_node = the_central_node
            configure(config)
            calculateOrbits()
        },
        getRadiusByNode: function(node)
        {
            return _getRadiusByNode(node)
        },
        getMaximalRadius: function()
        {
            return sizes[sizes.length - 1] + belt_sizes[belt_sizes.length - 1]
        },
        placeNodes: function()
        {
            for(var i = 0; i < nodes.length; i++)
            {
                var node = nodes[i]
                angle = Math.random() * Math.PI * 2
                R = _getRadiusByNode(node)
                node.x = R * Math.cos(angle) + central_node.x
                node.y = R * Math.sin(angle) + central_node.y
            }
        }
    }

    return publicSpace

} ())
