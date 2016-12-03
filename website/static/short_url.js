var ShortURL = function()
{
    // values in the default config are dummy - just to ilustrate the concept
    var config = {
        endpoint_get: '/get_shorthand_for_url_provided_in_get/',
        endpoint_use: '/use_shorthand/<shorthand>'
    }

    function getCurrentAddress()
    {
        var full_url = window.location.href.split('/')
        var address = ''

        for (var i = 3; i < full_url.length; i++)
        {
          address += '/'
          address += full_url[i]
        }

        return address
    }

    function getShortURL(btn, popover)
    {
        $.ajax({
            url: config.endpoint_get,
            type: 'GET',
            data: {address: encodeURIComponent(getCurrentAddress())},
            success: function(btn, popover)
            {
                return function(result)
                {
                    btn.data('shorthand', result)
                    popover.setContent()
                }
            }(btn, popover)
        })
    }

    function get_popup_html(){
        var btn = $(this)

        var shorthand = btn.data('shorthand')

        if(!shorthand)
        {
            var popover = btn.data('bs.popover')
            popover.tip().addClass('short-url-popover')
            getShortURL(btn, popover)
            return 'Generating short URL, just for you... <span class="glyphicon glyphicon-refresh glyphicon-spin"></span>'
        }

        return nunjucks.render(
            'short_url_popup.njk',
            {
                url: config.endpoint_use.replace('<shorthand>', shorthand)
            }
        )
    }

    var publicSpace = {
        init: function(endpoint_get, endpoint_use)
        {
            config.endpoint_get = decodeURIComponent(endpoint_get)
            config.endpoint_use = decodeURIComponent(endpoint_use)

            $('.short-url-btn[data-toggle="popover"]').popover(
                {
                    container: 'body',
                    placement: 'bottom',
                    trigger: 'click',
                    html: true,
                    content: get_popup_html
                }
            ).on('show.bs.popover', function()
                {
                    new Clipboard('.copy-btn')
                }
            )
        }
    }

    return publicSpace
}
