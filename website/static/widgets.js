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

      // initialize multiselect fields
      var to_multiselect = box.find('.multiselect')

      if(to_multiselect.length)
          to_multiselect.multiselect({
              onDropdownShow: function(event)
              {
                  var target = $(event.target)

                  var selected = target.find('li.active')

                  target.data('previously_selected', selected)
              },
              onDropdownHide: function(event)
              {
                  var target = $(event.target)

                  // selected counts also 'Select all' option
                  var selected = target.find('li.active')

                  // if there was not a change do not consider this action
                  if(checkEquality(selected, target.data('previously_selected')))
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

        init: function(widget_boxes, related_form, onupdate)
        {
            form = $(related_form)
            if(onupdate)
            {
                update = function ()
                {
                    onupdate(form)
                }
            }

            form.find('.save').hide()
            form.on(
                'change',
                '.widgets .widget select:not(.multiselect),.widgets .widget input:not(.multiselect)',
                update
            )

            /*
            for(var i = 0; i < widget_boxes.length; i++)
            {
                init_box(widget_boxes[i])
            }
            */
        }
    }

    return publicSpace
}())


