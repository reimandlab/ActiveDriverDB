var Export = function ()
{
    var svg_element
    var file_name
    var style_url
    var styles

    function get_styles()
    {
        $.ajax({
            url: style_url,
            type: 'GET',
            success: function(code)
            {
                styles = code
                publicSpace.export_svg()
            }
        })
    }

    var publicSpace = {

        init: function(element, title, style_address, custom_exporters, initial_style)
        {
            svg_element = element
            file_name = title
            style_url = style_address
            styles = initial_style

            $('.export_svg').click(publicSpace.export_svg)
            $('.export_print').click(publicSpace.export_print)

            if(custom_exporters)
            {
                publicSpace.set_custom_exporters(custom_exporters)
            }
        },
        set_custom_exporters: function(exporters)
        {
            var menu = $('.export-menu')

            // clear from old exporters
            menu.find('.custom_exporter').remove()

            exporters.forEach(
                function (exporter) {
                    var element = $(
                        '<li><a href="' + exporter.url + '" class="custom_exporter" target="_blank"><span class="glyphicon glyphicon-' + exporter.icon + '"></span> ' + exporter.name + '</a>'
                    )
                    menu.append(element)
                }
            )

        },
        update_title: function(title)
        {
            file_name = title
        },
        export_svg: function(event)
        {
            if(style_url && styles === undefined)
            {
                get_styles()
                return
            }

            var element_code = svg_element.innerHTML

            if(!element_code.match(/<svg[^>]+xmlns="http\:\/\/www\.w3\.org\/2000\/svg"/))
            {
                element_code = element_code.replace(
                    /<svg/,
                    '<svg xmlns="http://www.w3.org/2000/svg"'
                )
            }
            if(!element_code.match(/<svg[^>]+"http\:\/\/www\.w3\.org\/1999\/xlink"/)){
                element_code = element_code.replace(
                    /<svg/,
                    '<svg xmlns:xlink="http://www.w3.org/1999/xlink"'
                )
            }

            var css = ''
            if(styles)
                css += styles
            element_code = element_code.replace(
                /<svg(.*?)>/,
                '<svg $1><style type="text/css">/* <![CDATA[ */\n' + css + '\n/* ]]> */\n</style>'
            )
            var svg_blob = new Blob(
                [element_code],
                {type: 'image/svg+xml;charset=utf-8'}
            )
            var svg_content_url = URL.createObjectURL(svg_blob)
            var temp_link = document.createElement('a')
            temp_link.href = svg_content_url
            temp_link.style.display = 'none'
            temp_link.download = file_name + '.svg'
            document.body.appendChild(temp_link)
            temp_link.click()
            document.body.removeChild(temp_link)

            event.preventDefault()
        },
        export_print: function(event)
        {
            window.print()
            event.preventDefault()
        }
    }

    return publicSpace
}
