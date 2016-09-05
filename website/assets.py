from flask_assets import Bundle


def css_bundle(name, *args):
    return Bundle(
        *args,
        filters='cssutils',
        output='min/' + name + '.css'
    )


bundles = {
    'js_search': Bundle(
        'search.js',
        filters='rjsmin',
        output='min/search.js'
    ),
    'js_protein_view': Bundle(
        'common.js',
        'table.js',
        'needleplot.js',
        'filters.js',
        'tracks.js',
        filters='rjsmin',
        output='min/proteinView.js'
    ),
    'js_network_view': Bundle(
        'common.js',
        'orbits.js',
        'network.js',
        'filters.js',
        filters='rjsmin',
        output='min/networkView.js'
    ),
    'js_cms_editor': Bundle(
        'cms_editor.js',
        output='min/editor.js'
    ),
    'css_common': css_bundle(
        'style',
        'sass/style.css'
    ),
    'css_network': css_bundle(
        'network',
        'sass/network.css',
        'sass/filters.css'
    ),
    'css_protein': css_bundle(
        'protein',
        'sass/protein.css',
        'sass/tracks.css',
        'sass/filters.css'
    ),
    'css_search': css_bundle(
        'search',
        'sass/search.css'
    ),
    'css_page': css_bundle(
        'page',
        'sass/page.css'
    ),
    'css_admin': css_bundle(
        'admin',
        'sass/admin.css'
    )
}
