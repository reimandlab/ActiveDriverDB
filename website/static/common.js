function update_object(modified_obj, modyfing_obj)
{
    for(var key in modyfing_obj)
    {
        if(modyfing_obj.hasOwnProperty(key))
        {
            modified_obj[key] = modyfing_obj[key]
        }
    }
}

function prepareSVG(element)
{
    return d3
        .select(element)
        .append('svg')
        .attr('preserveAspectRatio', 'xMinYMin meet')
        .attr('class', 'svg-content-responsive')
}

function prepareZoom(min, max, callback)
{
    return d3.behavior.zoom()
       .scaleExtent([min, max])
       .on('zoom', callback)
       // allows to differentiante between pan-related clicks and normal clicks
       .on('zoomstart', function(){
           if(d3.event.sourceEvent) d3.event.sourceEvent.stopPropagation()
       })
}

function checkEquality(obj1, obj2)
{
    if(obj1.length !== obj2.length)
        return false

    return JSON.stringify(obj1) === JSON.stringify(obj2)
}


function get_remote_if_needed(new_config, name, callback)
{
    if(typeof new_config[name] === 'string')
    {
		$.ajax({
			url: new_config[name],
			type: 'GET',
			async: true,
			success: function(data)
			{
				new_config[name] = data
                callback()
			}
		})
    }
}
