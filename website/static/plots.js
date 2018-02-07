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