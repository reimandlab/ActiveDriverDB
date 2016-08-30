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

/* Polyfill from Mozilla Developer Network: */
if (!Array.isArray)
{
	Array.isArray = function(arg)
	{
		return Object.prototype.toString.call(arg) === '[object Array]'
	}
}
/* end of the polyfill */
