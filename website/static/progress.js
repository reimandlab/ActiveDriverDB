function Progress()
{
    var url;
    var progress_span, progress_bar;
    var state_failure, state_progress, state_pending;

    function set_progress(percent)
    {
        progress_span.html(percent);
        progress_bar.css({width: percent + '%'})
        progress_bar.attr('aria-valuenow', percent)
    }

    function update_progress()
    {
        $.ajax({
            url: url,
            type: 'GET',
            success: function (response) {
                if (response.status === 'SUCCESS') {
                    set_progress(100)
                    window.location.reload()
                }
                else if(response.status === 'PROGRESS')
                {
                    state_pending.hide()
                    state_progress.removeClass('hidden')
                    set_progress(response.progress)
                    window.setTimeout(update_progress, 1000)
                }
                else if(response.failure === 'FAILURE')
                {
                    state_progress.hide()
                    state_pending.hide()
                    state_failure.removeClass('hidden')
                }
            }
        })
    }
    return {
        'init': function(new_config)
        {
            url = new_config.url
            progress_span = $('#progress-percent')
            progress_bar = $('#progress-bar')
            state_failure = $('.state-failure')
            state_pending = $('.state-pending')
            state_progress = $('.state-progress')
            window.setTimeout(update_progress, 1000)

        }
    }

}
