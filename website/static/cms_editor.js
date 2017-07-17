function init_tinymce(config)
{
    var default_config = {
        selector: 'textarea',
        body_class: 'page-content',
        content_css : [
            '/static/min/page.css',
            'https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css'
        ],
        height: 260,
        branding: false,
        browser_spellcheck: true,
        plugins : 'anchor advlist autolink link image lists charmap print preview fullscreen table imagetools textcolor colorpicker searchreplace code codesample autoresize visualblocks',
        toolbar: 'undo redo | styleselect | bold italic | alignleft aligncenter alignright alignjustify | bullist numlist outdent indent | link image | codesample visualblocks',
        table_default_attributes: {
            class: 'table table-bordered table-hover'
        },
        autoresize_max_height: 600,
        table_class_list: [
            {title: 'Default', value: 'table table-bordered table-hover'},
            {title: 'Hover, Striped', value: 'table table-bordered table-hover table-striped '},
            {title: 'Hover, Striped, without borders', value: 'table table-hover table-striped table-borderless'},
            {title: 'Hover, without borders', value: 'table table-hover table-borderless'},
            {title: 'Outer Border Only', value: 'table table-outer-border'},
            {title: 'Clear', value: 'table table-borderless'}
        ],
        codesample_languages: [
            {text: 'HTML/XML', value: 'markup'},
            {text: 'JavaScript', value: 'javascript'},
            {text: 'CSS', value: 'css'},
            {text: 'Python', value: 'python'},
            {text: 'Bash', value: 'bash'}
        ]
    }

    $(document).ready(function(){

        update_object(default_config, config)

        var editors = $(default_config.selector);
        delete default_config.selector

        editors.each(
            function () {
                var config = {}
                update_object(config, default_config)
                if($(this).data('compact'))
                {
                    config.elementpath = false
                    config.statusbar = false
                    config.menubar = false
                    config.content_style = 'body{padding-bottom:0!important}'
                }

                config.target = this
                tinymce.init(config)
            }
        )
    })
}
