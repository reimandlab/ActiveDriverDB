/**
 * Zoom is responsible for zooming and panning of canvas and keeping it in borders of specified viewport.
 *
 * Following terms are used in this module:
 * - canvas: an html element (presumably <svg>) to be zoomed and moved
 * - viewport: a container restricting movement and scale of the canvas
 *
 * The CSSZoom was implemented using CSS transitions to speed up zooming and panning on older browsers,
 * where support for SVG transitions was not hardware-accelerated as CSS3 transitions are.
 * Currently some browsers support SVG transitions much smoother but still,
 * the older browser keep a major share in the market.
 *
 * Some browsers (Safari family) seems to have problems with CSS or element transitions executed on SVG elements;
 * for those, and for brave future where all browsers support all transitions equally there is Zoom fallback
 * which may be returned by Zoom initializer if it decides it is a better to use the simpler, SVG-only transitions.
 *
 * CSSZoom and Zoom fallback should be merged into a class hierarchy in future when support for ES6 matures:
 * see: http://caniuse.com/es6-class. At time of writing classes are supported in browsers of 73.97% users.
 */
var Zoom = function(css_zoom)
{
    var svg;
    var min;
    var max;
    var config;
    var zoom;
    var viewport;
    var svg_canvas;

    var viewport_size = [];

    function callback()
    {
        transform(d3.event.translate, d3.event.scale, 0);
        config.on_move(this)
    }

    function transform(translate, scale, animation_speed)
    {
        zoom.translate(translate);
        zoom.scale(scale);

        if(animation_speed)
        {
            svg_canvas.transition()
                .duration(animation_speed)
                .attr('transform', 'translate(' + translate + ')scale(' + scale + ')');
        }
        else
        {
            svg_canvas
                .attr('transform', 'translate(' + translate + ')scale(' + scale + ')');
        }
    }

    function set_viewport_size(width, height)
    {
        viewport_size[0] = width;
        viewport_size[1] = height;

        svg.attr('viewBox', '0 0 ' + width + ' ' + height);
        svg.attr('width', width + 'px');
        svg.attr('height', height + 'px');
        svg.style('transform-origin', 'top left');
    }

    /** Trim the new_scale to pre-set limit (min & max) */
    function trim_scale(new_scale)
    {
        zoom.scale(new_scale);
        return zoom.scale();
    }

    var public_space = {
        init: function (user_config, new_transform) {
            if(new_transform)
                transform = new_transform

            config = user_config;
            svg = config.element;
            svg_canvas = config.inner_element;
            min = config.min;
            max = config.max;

            zoom = prepareZoom(min, max, callback);

            viewport = d3.select(config.viewport);
            viewport.call(zoom).on('dblclick.zoom', null)
        },
        viewport_to_canvas: function(position){return position},
        canvas_to_viewport: function(position){return position},
        set_viewport_size: set_viewport_size,
        set_zoom: function(new_scale)
        {
            new_scale = trim_scale(new_scale)

            var translate = zoom.translate();

            // apply the new zoom
            transform(translate, new_scale, 600)
        },
        center_on: function(position, radius, animation_speed)
        {
            animation_speed = (typeof animation_speed === 'undefined') ? 750: animation_speed;

            var scale = Math.min(viewport_size[0], viewport_size[1]) / radius;

            scale = trim_scale(scale)

            position[0] *= -scale;
            position[1] *= -scale;
            position[0] += viewport_size[0] / 2;
            position[1] += viewport_size[1] / 2;

            transform(position, scale, animation_speed)
        },
        get_zoom: function(){
            return zoom.scale();
        }
    }

    var CSS_Zoom = function(my_parent)
    {
        var parent = my_parent
        var canvas_size = [];

        function transform(translate, scale, animation_speed)
        {
            // canvas_size[0] * scale represents real width of an svg element after scaling
            translate[0] = Math.min(0, Math.max(viewport_size[0] - canvas_size[0] * scale, translate[0]));
            translate[1] = Math.min(0, Math.max(viewport_size[1] - canvas_size[1] * scale, translate[1]));

            // parent.transform() could be used but it adds overhead of additional call in
            // function which could be called hundreds times per second
            zoom.translate(translate);
            zoom.scale(scale);

            if(animation_speed)
            {
                svg.transition()
                    .duration(animation_speed)
                    .attr('transform', 'translate(' + translate + ')scale(' + scale + ')');
            }
            else
            {
                svg
                    .attr('transform', 'translate(' + translate + ')scale(' + scale + ')');
            }
        }

        function set_viewport_size(width, height)
        {
            canvas_size[0] = Math.max(width * config.max, width / config.min);
            canvas_size[1] = Math.max(height * config.max, height / config.min);

            parent.set_viewport_size(canvas_size[0], canvas_size[1])

            viewport_size[0] = width;
            viewport_size[1] = height;
        }

        function viewport_to_canvas(position)
        {
            return [
                position[0] / viewport_size[0] * canvas_size[0],
                position[1] / viewport_size[1] * canvas_size[1]
            ]
        }

        function canvas_to_viewport(position)
        {
            return [
                position[0] * viewport_size[0] / canvas_size[0],
                position[1] * viewport_size[1] / canvas_size[1]
            ]
        }

        /**
         * Configuration object for Zoom.
         * @typedef {Object} Config
         * @property {number} min - 1 / how many times the element can be zoomed-out?
         * e.g. 1/5 means that when maximally zoomed out, the content will be of 1/5 its original size
         * @property {max} max - how many times the element can be zoomed-in?
         * e.g. 2 means that when maximally zoomed in, the content will be twice its original size
         * @property {function} on_move - callback called after each zoom/move transformation
         * @property {D3jsElement} element - the element to be zoomed and panned (canvas)
         * @property {HTMLElement} viewport - element defining boundaries of the transformed element
         */
        var public_space = {
            /**
             * Initialize Zoom.
             * @param {Config} user_config
             */
            init: function(user_config)
            {
                parent.init(user_config, transform)
            },
            viewport_to_canvas: viewport_to_canvas,
            canvas_to_viewport: canvas_to_viewport,
            set_viewport_size: set_viewport_size,
            set_zoom: function(new_scale)
            {
                var old_scale = zoom.scale();

                new_scale = trim_scale(new_scale)

                // keep the focus in the same place as it was before zooming
                var translate = zoom.translate();
                var factor = old_scale - new_scale;
                translate = [
                    translate[0] + factor * canvas_size[0] / 2,
                    translate[1] + factor * canvas_size[1] / 2
                ];

                // apply the new zoom
                transform(translate, new_scale, 600)
            }
        }

        return $.extend({}, parent, public_space);
    }

    if(css_zoom)
        return CSS_Zoom(public_space)
    else
        return public_space
}

var CSSZoom = function()
{
    return Zoom(true)
}

function choose_best_zoom()
{
    var agent = navigator.userAgent;
    var is_ie = !!document.documentMode;
    var is_edge = agent.indexOf('Edge') > -1;
    var is_safari = agent.indexOf('Safari') > -1;
    var is_chrome = agent.indexOf('Chrome') > -1;
    if (is_safari && is_chrome)
        is_safari = false;

    if(is_safari || is_edge || is_ie)
        return Zoom;
    else
        return CSSZoom;
}