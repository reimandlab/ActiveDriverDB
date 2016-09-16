tinymce.init({
    selector: 'textarea',
    body_class: 'page-content',
    content_css : [
        '/static/min/page.css',
        '/static/thirdparty/bootstrap/css/bootstrap.min.css'
    ],
    height: 160,
    browser_spellcheck: true,
    plugins : 'anchor advlist autolink link image lists charmap print preview fullscreen table imagetools textcolor colorpicker searchreplace',
    table_default_attributes: {
        class: 'table table-bordered table-hover'
    },
    table_class_list: [
        {title: 'Default', value: 'table table-bordered table-hover'},
        {title: 'Striped', value: 'table table-bordered table-hover table-striped'},
        {title: 'Without borders', value: 'table table-hover table-striped'},
        {title: 'Striped, without borders', value: 'table table-hover table-striped'}
    ]

})
