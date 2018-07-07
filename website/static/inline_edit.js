var InlineEditManager = function()
{
    // values in the default config are dummy - just to illustrate the concept
    var config = {
        endpoint_save: '/save_message/',
        nltobr: true
    }

    function updateMessage(editable_box, new_content)
    {
        var content_div = editable_box.find('.content')
        if(config.nltobr)
            new_content = new_content.replace(/\n/g, '<br class="automatic">')
        return content_div.html(new_content)
    }

    function getContent(editable_box)
    {
        var content_div = editable_box.find('.content')
        var content = content_div.html()
        if(config.nltobr)
            content = content.replace(/<br class="automatic">/g, '\n')
        return content
    }

    function saveMessage(editable_box)
    {
        $.ajax({
            url: config.endpoint_save,
            type: 'POST',
            data: {
                entry_id: editable_box.data('id'),
                old_content: getContent(editable_box),
                new_content: editable_box.find('.new-content').val()
            },
            success: function(editable_box)
            {
                return function(result)
                {
                    var message = ''

                    if(result.status === 409)
                    {
                        var current_content = getContent(editable_box)
                        if(current_content === result.content)
                            result.status = 200
                        else
                        {
                            updateMessage(editable_box, result.content)
                            message =
                                '<strong>Someone has edited this entry from another window!</strong> ' +
                                'The current text is: ' +
                                '<textarea>' + result.content + '</textarea><br>' +
                                'Press save if you wish to overwrite this text.'
                        }
                    }

                    if(result.status === 200)
                    {
                        updateMessage(editable_box, result.content)
                        return endEdition(editable_box)
                    }

                    if(result.status === 509)
                        message = 'Something went wrong'

                    if(message)
                    {
                        editable_box.find('.feedback').html(message)
                        editable_box.find('.feedback').show()
                    }
                }
            }(editable_box)
        })
    }

    function rejectEdit(editable_box)
    {
        var unchanged_content = getContent(editable_box)
        editable_box.find('.new-content').val(unchanged_content)
        endEdition(editable_box)
    }

    function endEdition(editable_box)
    {
        editable_box.find('.edit-form').hide()
        editable_box.find('.edit-btn').show()
        editable_box.find('.content').show()
        editable_box.find('.feedback').hide()
    }

    var publicSpace = {
        init: function(endpoint_save, box_selector, nltobr)
        {
            config.endpoint_save = decodeURIComponent(endpoint_save)
            config.nltobr = nltobr

            var inline_editable_box = $(box_selector)
            inline_editable_box.find('.edit-btn').click(
                function()
                {
                    var edit_btn = $(this)
                    edit_btn.hide()

                    var editable_box = edit_btn.closest(box_selector)
                    editable_box.find('.content').hide()
                    editable_box.find('.edit-form').show()

                    editable_box.find('.save-btn').off().click(
                        function(editable_box){ return function(){saveMessage(editable_box)} }(editable_box)
                    )
                    editable_box.find('.reject-btn').off().click(
                        function(editable_box){ return function(){rejectEdit(editable_box)} }(editable_box)
                    )
                }
            )


        }
    }

    return publicSpace
}


function create_help_manager(endpoint_save)
{
    var inline_help_box = $('.inline-help')
    inline_help_box.find('.dropdown-menu').on(
        'click',
        function(event){event.stopPropagation()}
    )
    return InlineEditManager().init(endpoint_save, '.inline-help', true)
}

function create_text_manager(endpoint_save)
{
    return InlineEditManager().init(endpoint_save, '.text-entry', false)
}
