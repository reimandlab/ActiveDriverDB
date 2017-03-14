function update_object(modified_obj, modifying_obj)
{
    for(var key in modifying_obj)
    {
        if(modifying_obj.hasOwnProperty(key))
        {
            modified_obj[key] = modifying_obj[key]
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
       // allows to differentiate between pan-related clicks and normal clicks
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


function get_url_params()
{
    // in future URLSearchParams would do the job
    var params_string = decodeURIComponent(window.location.search)
    params_string = params_string.substr(1) // remove '?' character from the beginning
    var params_list = params_string.split('&')
    var params = {}
    for(var i = 0; i < params_list.length; i++)
    {
      var param = params_list[i].split('=')
      var key = param[0]
      var value = param[1]
      if(key)
        params[key] = value
    }
    return params
}


function affix(element, bottom_element)
{
    // fix the width (so it's set in pixels)
    element.css('position', 'static')
    element.css('width', '')
    element.width(element.width())

    element.affix({
        offset: {
            top: function () {
                return (this.top = element.offset().top)
            },
            bottom: function () {
                return (this.bottom = bottom_element.outerHeight(true))
            }
        }
    })

    var parent = $(element.parent())
    parent.css('min-height', '')
    parent.css('min-height', parent.height())

    element.css('position', '')

    $(window).on(
        'resize', function()
        {
            affix(element, bottom_element)
        }
    )
}
