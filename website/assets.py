from flask_assets import Bundle


def css_bundle(name, *args):
    return Bundle(
        *args,
        # filters='cssutils',   # cssutils breaks keyframes :(
        output='min/' + name + '.css'
    )


bundles = {
    'js_search_bar': Bundle(
        'searchbar.js',
        filters='rjsmin',
        output='min/searchbar.js'
    ),
    'js_search': Bundle(
        'search.js',
        filters='rjsmin',
        output='min/search.js'
    ),
    'js_protein_view': Bundle(
        'common.js',
        'widgets.js',
        'table.js',
        'tooltip.js',
        'needleplot.js',
        'tracks.js',
        'export.js',
        'short_url.js',
        filters='rjsmin',
        output='min/proteinView.js'
    ),
    'js_network_view': Bundle(
        'common.js',
        'widgets.js',
        'orbits.js',
        'tooltip.js',
        'network.js',
        'export.js',
        'short_url.js',
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
        'sass/widgets.css',
        'sass/tooltip.css',
        'sass/network.css'
    ),
    'css_protein': css_bundle(
        'protein',
        'sass/widgets.css',
        'sass/tooltip.css',
        'sass/protein.css',
        'sass/tracks.css'
    ),
    'css_gene': css_bundle(
        'gene',
        'sass/gene.css'
    ),
    'css_print': css_bundle(
        'print',
        'sass/print.css'
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
