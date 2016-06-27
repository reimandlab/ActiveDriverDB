
var NeedlePlot = (function ()
{

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

            var mutneedles = require("muts-needle-plot")

            var legends = {
              x: data.name + " Amino Acid sequence (" + data.refseq + ")",
              y: "# of mutations in " + data.name
            }

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

            var instance = new mutneedles(plotConfig)
		}
	}

	return publicSpace
}())


