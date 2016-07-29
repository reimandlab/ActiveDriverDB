mutneedles = require("muts-needle-plot")

var NeedlePlot = function ()
{
    var instance
    var element

    var colorMap = {
      "missense": "yellow",
      "synonymous": "lightblue",
      "truncating": "red",
      "splice-site": "orange",
      "other": "grey"
    }


	var publicSpace = {
		init: function(data)
		{

            var legends = {
              x: data.name + " Amino Acid sequence (" + data.refseq + ")",
              y: "# of mutations in " + data.name
            }

            element = data.element

            var plotConfig = {
              minCoord:      0,
              maxCoord:      data.sequenceLength,
              targetElement: data.element,
              mutationData:  data.mutations,
              regionData:    data.sites,
              colorMap:      colorMap,
              legends:       legends,
              width: 600,
              height: 400,
              responsive: 'resize'
            }

            instance = new mutneedles(plotConfig)
		},
        setZoom: function(scale, trigger_callback)
        {
            $(element).css('transform', 'scaleX(' + scale + ')')
        }
	}

	return publicSpace
}
