var Widgets = (function () {
    var form
    var select_sth_popover = {
        content: 'You should select at least one option',
        placement: 'top',
        trigger: 'manual'
    }

    function update() {
        form.submit()
    }

    function multiselect(inputs)
    {
        if(inputs.length === 0)
            return false;

        inputs.multiselect({
            onDropdownShow: function(event)
            {
                var target = $(event.target);

                var selected = target.find('li.active');

                target.data('previously_selected', selected)
            },
            onDropdownHide: function(event)
            {
                var target = $(event.target);

                // selected counts also 'Select all' option
                var selected = target.find('li.active');

                // if there was not a change do not consider this action
                if(checkEquality(selected, target.data('previously_selected')))
                {
                    return true
                }
                if (selected.length < 1)
                {
                    target.parent().popover(select_sth_popover).popover('show');
                    return false
                }
                else {
                    target.parent().popover('hide');
                    update()
                }

            },
            onChange: function(option, checked)
            {
                if(checked) {
                    $(option).parent().parent().popover('hide')
                }
            },
            includeSelectAllOption: true,
            dropRight: true,
            allSelectedText: $(this).data('all-selected-text')
        })
    }

    /**
     * Initialize checkbox lists, enabling "check all" functionality.
     * Special checkbox with class 'programmatic', wrapped in 'check-all'
     * li element is required for this functionality.
     * @param {jQuery} uls - lists of checkboxes
     */
    function checkbox_list(uls)
    {
        function block(ul)
        {
            ul.popover('show');
            ul.addClass('block');
        }
        function release(ul)
        {
            ul.popover('hide');
            ul.removeClass('block');
        }

        uls.each(function() {
            var ul = $(this);
            var checkboxes = ul.find('input[type=checkbox]:not(.programmatic)');
            var check_all = ul.find('.check-all input');
            ul.popover(select_sth_popover);

            check_all.click(function () {
                checkboxes.prop('checked', this.checked);

                if (this.checked) {
                    release(ul);
                    $(checkboxes[0]).trigger('change')
                }
                else {
                    block(ul);
                }
            });

            checkboxes.change(function () {
                if (this.checked) {
                    // at least one checked
                    release(ul);
                    // all checked
                    if(checkboxes.filter(':not(:checked)').length === 0) {
                        check_all.prop('checked', true)
                    }

                }
                // all unchecked
                else if (checkboxes.filter(':checked').length === 0) {
                    block(ul);
                    event.stopImmediatePropagation()
                }
                // at least one un-checked, but not all
                else {
                    check_all.prop('checked', false)
                }
            })
        })
    }

    return {

        // TODO: remove "form" from here at all - widgets should not be responsible for forms
        init: function(form_to_submit, onupdate)
        {
            form = $(form_to_submit);
            if(onupdate)
            {
                update = function ()
                {
                    onupdate(form)
                }
            }

            form.find('.save').hide();
            form.on(
                'change',
                '.widget select:not(.multiselect),.widget input:not(.programmatic)',
                update
            );

            multiselect(form.find('.widget .multiselect'));
            checkbox_list(form.find('.widget .checkbox-list'));
        }
    };

}());


