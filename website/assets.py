from flask_assets import Bundle
from flask import Markup


def css_bundle(name, *args):
    return Bundle(
        *args,
        # filters='cssutils',   # cssutils breaks keyframes :(
        output='min/' + name + '.css'
    )


class Resource:
    """Represents a resource which could be fetched from a content
    delivery network (cdn) or from a local static directory."""

    def __init__(self, url, integrity=None, only_cdn=False):
        """

        Args:
            url: full location of the resource (including protocol specification)
            integrity: hash code for integrity checkup (SRI)
            only_cdn: does the resource require to be accessed remotely?
        """
        self.url = url
        self.integrity = integrity
        self.only_cdn = only_cdn


class CSSResource(Resource):
    pass


class JSResource(Resource):
    pass


class DependencyManager:

    third_party = {
        'jquery': JSResource(
            'https://code.jquery.com/jquery-1.12.4.min.js',
            'sha256-ZosEbRLbNQzLpnKIkEdrPv7lOy9C27hHQ+Xp8a4MxAQ='
        ),
        'bootstrap_css': CSSResource(
            'https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css',
            'sha384-BVYiiSIFeK1dGmJRAkycuHAHRg32OmUcww7on3RYdg4Va+PmSTsz/K68vbdEjh4u',
            only_cdn=True
        ),
        'bootstrap_js': JSResource(
            'https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/js/bootstrap.min.js',
            'sha384-Tc5IQib027qvyjSMfHjOMaLkfuWVxZxUPnCJA7l2mCWNIpG9mGCD8wGNIcPD7Txa'
        ),
        'prism': JSResource(
            'https://cdnjs.cloudflare.com/ajax/libs/prism/1.6.0/prism.min.js',
            'sha256-Zb9yKJ/cfs+jG/zIOFL0QEuXr2CDKF7FR5YBJY3No+c='
        ),
        'prism_bash': JSResource(
            'https://cdnjs.cloudflare.com/ajax/libs/prism/1.6.0/components/prism-bash.min.js',
            'sha256-Cpwt90TIzSA/DB4pWWhjvGMLFzqRuClV20inTWKgJ2w='
        ),
        'prism_css': CSSResource(
            'https://cdnjs.cloudflare.com/ajax/libs/prism/1.6.0/themes/prism.min.css',
            'sha256-vtR0hSWRc3Tb26iuN2oZHt3KRUomwTufNIf5/4oeCyg='
        ),
        'nunjucks': JSResource(
            'https://cdnjs.cloudflare.com/ajax/libs/nunjucks/3.0.0/nunjucks.min.js',
            'sha256-LWvp8rf/ha5W5zb5rGjypfi/b8w5Yo0Lm+W6ccH3ejA='
        ),
        'nunjucks_slim': JSResource(
            'https://cdnjs.cloudflare.com/ajax/libs/nunjucks/3.0.0/nunjucks-slim.min.js',
            'sha256-jR3u71exa6Z+mFgFrFsAZnqAIFbpVBzyynMUTq7fSc4='
        ),
        'bootstrap_table': JSResource(
            'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-table/1.11.1/bootstrap-table.min.js',
            'sha256-eXHLyyVI+v6X1wbfg9NB05IWqOqY4E9185nHZgeDIhg='
        ),
        'bootstrap_table_css': CSSResource(
            'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-table/1.11.1/bootstrap-table.min.css',
            'sha256-eU4xmpfQx1HSi5q1q2rHNcMEzTNJov7r2Wr/6zF3ANc='
        ),
        'bootstrap_table_export': JSResource(
            'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-table/1.11.1/extensions/export/bootstrap-table-export.min.js',
            'sha256-bNaAGj3n4fpGsbo2WDr9JJoalh5/CSrz4wlkbk3TS88='
        ),
        'd3.js': JSResource(
            'https://cdnjs.cloudflare.com/ajax/libs/d3/3.5.17/d3.min.js',
            'sha256-dsOXGNHAo/syFnazt+KTBsCQeRmlcW1XKL0bCK4Baec='
        ),
        'clipboard.js': JSResource(
            'https://cdnjs.cloudflare.com/ajax/libs/clipboard.js/1.6.1/clipboard.min.js',
            'sha256-El0fEiD3YOM7uIVZztyQzmbbPlgEj0oJVxRWziUh4UE='
        ),
        'md5': JSResource(
            'https://cdnjs.cloudflare.com/ajax/libs/blueimp-md5/2.7.0/js/md5.min.js',
            'sha256-I0CACboBQ1ky299/4LVi2tzEhCOfx1e7LbCcFhn7M8Y='
        ),
        'history_api': JSResource(
            'https://cdnjs.cloudflare.com/ajax/libs/html5-history-api/4.2.8/history.ielte7.min.js',
            'sha256-W+ihVak5YZJG2/K/LZZnaL7LHxu0dl0Wb9lo77tnVEA='
        ),
        'table_export': JSResource(
            'https://rawgit.com/hhurz/tableExport.jquery.plugin/master/tableExport.js'
        ),
        'html5shiv': JSResource(
            'https://cdnjs.cloudflare.com/ajax/libs/html5shiv/3.7.3/html5shiv.min.js',
            'sha256-3Jy/GbSLrg0o9y5Z5n1uw0qxZECH7C6OQpVBgNFYa0g='
        ),
        'tinymce': JSResource(
            'https://cdnjs.cloudflare.com/ajax/libs/tinymce/4.6.1/tinymce.min.js',
            'sha256-GnWmLZ0UK0TTmZEj5w4U6SLOnEJlalLnsOLDcUXzYyc=',
            only_cdn=True
        )
    }

    tags_and_url_key_words = {
        JSResource: 'script src',
        CSSResource: 'link rel="stylesheet" href'
    }

    def __init__(self, app):
        self.app = app
        self.use_cdn = self.app.config.get('USE_CONTENT_DELIVERY_NETWORK', True)

    def get_dependency(self, name):

        resource = self.third_party[name]

        if self.use_cdn or resource.only_cdn:
            return self.build_cdn_markup(resource)
        else:
            return self.build_local_markup(resource)

    def build_cdn_markup(self, resource):
        return self.build_markup(type(resource), resource.url, resource.integrity)

    def build_local_markup(self, resource):
        from urllib.request import urlretrieve
        from os.path import dirname
        from os.path import exists
        from os.path import realpath
        from os import makedirs

        path = 'static/thirdparty/' + '/'.join(resource.url.split('/')[3:])

        real_path = dirname(realpath(__file__)) + '/' + path
        if not exists(real_path):
            dir_path = dirname(real_path)
            if dir_path:
                makedirs(dir_path, exist_ok=True)
            urlretrieve(resource.url, real_path)

        return self.build_markup(type(resource), '/' + path)

    def build_markup(self, resource_type, url, integrity=None):
        tag = self.tags_and_url_key_words[resource_type]

        if integrity:
            markup = '<{tag}="{url}" integrity="{integrity}" crossorigin="anonymous">'.format(
                tag=tag,
                url=url,
                integrity=integrity
            )
        else:
            markup = '<{tag}="{url}">'.format(
                tag=tag,
                url=url,
            )
        if resource_type is JSResource:
            markup += '</script>'

        return Markup(markup)


bundles = {
    'js_search_bar': Bundle(
        'searchbar.js',
        filters='rjsmin',
        output='min/searchbar.js'
    ),
    'js_search': Bundle(
        'common.js',
        'widgets.js',
        'search.js',
        filters='rjsmin',
        output='min/search.js'
    ),
    'js_protein_view': Bundle(
        'common.js',
        'filters.js',
        'widgets.js',
        'tooltip.js',
        'kinase_tooltip.js',
        'table.js',
        'needleplot.js',
        'tracks.js',
        'export.js',
        'short_url.js',
        filters='rjsmin',
        output='min/proteinView.js'
    ),
    'js_mutation_view': Bundle(
        'common.js',
        'tooltip.js',
        'kinase_tooltip.js',
        'export.js',
        'short_url.js',
        filters='rjsmin',
        output='min/mutationView.js'
    ),
    'js_gene_view': Bundle(
        'common.js',
        'widgets.js',
        filters='rjsmin',
        output='min/geneView.js'
    ),
    'js_network_view': Bundle(
        'common.js',
        'filters.js',
        'widgets.js',
        'orbits.js',
        'tooltip.js',
        'zoom.js',
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
        'sass/widgets.css',
        'sass/gene.css'
    ),
    'css_mutation': css_bundle(
        'mutation',
        'sass/tooltip.css',
        'sass/mutation.css'
    ),
    'css_print': css_bundle(
        'print',
        'sass/print.css'
    ),
    'css_search': css_bundle(
        'search',
        'sass/widgets.css',
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
