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
}
