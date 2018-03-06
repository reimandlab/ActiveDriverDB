(function() {

    var resize_all = function() {
        if(Plotly === undefined) return

        $('.js-plotly-plot').each(function (i) {
            Plotly.Plots.resize(this);
        })
    };

    $(document).on('click', '.nav-tabs li', function(){
        if(Plotly === undefined) return

        var tab = $(this).find('a').attr('href')
        var plot = $(tab).find('.js-plotly-plot').get(0)
        if(plot !== undefined)
            Plotly.Plots.resize(plot);
    })
    window.onresize = resize_all

})()

plot = (function () {

    function save_svg(gd) {
        console.log($(gd).width())
        Plotly.downloadImage(gd, {
            format: 'svg',
            width: $(gd).width(),
            height: $(gd).height(),
            filename: gd.id
        })
    }

    function plot(element_id, data, layout){

        var COMMON_PLOT_OPTIONS = {
            displaylogo: false,
            modeBarButtonsToAdd: [{
                name: 'Save as SVG',
                icon: Plotly.Icons.camera,
                click: save_svg
            }]
        }
        return Plotly.newPlot(element_id, data, layout, COMMON_PLOT_OPTIONS)
    }

    return plot
})()
