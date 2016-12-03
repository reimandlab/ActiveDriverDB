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

    function getShortURL(btn, dropdown)
    {
        $.ajax({
            url: config.endpoint_get,
            type: 'GET',
            data: {address: encodeURIComponent(getCurrentAddress())},
            success: function(btn, dropdown)
            {
                return function(result)
                {
                    btn.data('shorthand', result)
                    var html = get_html(btn)
                    dropdown.html(html)
                }
            }(btn, dropdown)
        })
    }

    function get_html(btn, dropdown){

        var shorthand = btn.data('shorthand')

        if(!shorthand)
        {
            getShortURL(btn, dropdown)
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

            var dropdown_wrapper = $('.short-url-btn').parent()

            dropdown_wrapper.on('show.bs.dropdown', function()
                {
                    var btn = $(this).find('.short-url-btn')
                    var dropdown = $(this).find('.dropdown-menu')
                    dropdown.html(get_html(btn, dropdown))

                    var copy_btn = dropdown.find('.copy-btn')[0]
                    if(copy_btn)
                        new Clipboard(copy_btn)
                }
            )
            dropdown_wrapper.find('.dropdown-menu').on(
                'click',
                function(event){event.stopPropagation()}
            )

        }
    }

    return publicSpace
}
