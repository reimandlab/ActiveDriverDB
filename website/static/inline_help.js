var HelpManager = function()
{
    // values in the default config are dummy - just to illustrate the concept
    var config = {
        endpoint_save: '/save_help_message/'
    }

    function updateHelpMessage(help_box, new_content)
    {
        var content_div = help_box.find('.content')
        new_content = new_content.replace(/\n/g, '<br>')
        return content_div.html(new_content)
    }


    function getHelpContent(help_box)
    {
        var content_div = help_box.find('.content')
        return content_div.html().replace(/<br>/g, '\n')
    }

    function saveHelpMessage(help_box)
    {
        $.ajax({
            url: config.endpoint_save,
            type: 'POST',
            data: {
                help_id: help_box.data('id'),
                old_content: getHelpContent(help_box),
                new_content: help_box.find('.new-content').val()
            },
            success: function(help_box)
            {
                return function(result)
                {
                    var message = ''

                    if(result.status === 409)
                    {
                        var current_content = getHelpContent(help_box)
                        if(current_content === result.content)
                            result.status = 200
                        else
                        {
                            updateHelpMessage(help_box, result.content)
                            message =
                                '<strong>Someone has edited this entry from another window!</strong> ' +
                                'The current help text is: ' +
                                '<textarea>' + result.content + '</textarea><br>' +
                                'Press save if you wish to overwrite this text.'
                        }
                    }

                    if(result.status === 200)
                    {
                        updateHelpMessage(help_box, result.content)
                        return endEdition(help_box)
                    }

                    if(result.status === 509)
                        message = 'Something went wrong'

                    if(message)
                    {
                        help_box.find('.feedback').html(message)
                        help_box.find('.feedback').show()
                    }
                }
            }(help_box)
        })
    }

    function rejectEdit(help_box)
    {
        var unchanged_content = getHelpContent(help_box)
        help_box.find('.new-content').val(unchanged_content)
        endEdition(help_box)
    }

    function endEdition(help_box)
    {
        help_box.find('.edit-form').hide()
        help_box.find('.edit-btn').show()
        help_box.find('.content').show()
        help_box.find('.feedback').hide()
    }

    var publicSpace = {
        init: function(endpoint_save)
        {
            config.endpoint_save = decodeURIComponent(endpoint_save)

            var inline_help_box = $('.inline-help')
            inline_help_box.find('.edit-btn').click(
                function()
                {
                    var help_btn = $(this)
                    help_btn.hide()

                    var help_box = help_btn.closest('.inline-help')
                    help_box.find('.content').hide()
                    help_box.find('.edit-form').show()

                    help_box.find('.save-btn').off().click(
                        function(help_box){ return function(){saveHelpMessage(help_box)} }(help_box)
                    )
                    help_box.find('.reject-btn').off().click(
                        function(help_box){ return function(){rejectEdit(help_box)} }(help_box)
                    )
                }
            )

            inline_help_box.find('.dropdown-menu').on(
                'click',
                function(event){event.stopPropagation()}
            )

        }
    }

    return publicSpace
}
