var Widgets = (function ()
{
    var form

    function update(e)
    {
        form.submit()
    }

  function init_box(widget_box)
  {

      var box = $(widget_box)

      form.find('.save').hide()

      var widgets = box.find('.widget')
      for(var j = 0; j < widgets.length; j++)
      {
          var widget = widgets[j]
          var select = $(widget).find('select,input').not('.multiselect')
          select.change(update)
      }

      // initialize multiselect fields
      var to_multiselect = box.find('.multiselect')

      if(to_multiselect.length)
          to_multiselect.multiselect({
              onDropdownShow: function(event)
              {
                  var target = $(event.target)

                  var selected = target.find('li.active')

                  target.data('prevoiously_selected', selected)
              },
              onDropdownHide: function(event)
              {
                  var target = $(event.target)

                  // selected counts also 'Select all' option
                  var selected = target.find('li.active')

                  // if there was not a change do not consider this action
                  if(checkEquality(selected, target.data('prevoiously_selected')))
                  {
                      return true
                  }
                  if (selected.length < 1)
                  {
                      target.parent().popover({
                          content: 'You should select at least one option',
                          placement: 'top',
                          trigger: 'manual'
                      }).popover('show')
                      return false
                  }
                  else {
                      target.parent().popover('hide')
                      update()
                  }

              },
              onChange: function(option, checked)
              {
                  if(checked)
                      $(option).parent().parent().popover('hide')
              },
              includeSelectAllOption: true,
              dropRight: true,
              allSelectedText: $(this).data('all-selected-text')
          })
  }

	var publicSpace = {

		init: function(widget_boxes, related_form)
		{
            form = $(related_form)
            for(var i = 0; i < widget_boxes.length; i++)
            {
                init_box(widget_boxes[i])
            }
		}
	}

	return publicSpace
}())


Widgets.init($('.widgets'), $('.widget-form')[0])
