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
