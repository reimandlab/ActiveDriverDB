from pathlib import Path
from types import SimpleNamespace

from pandas import DataFrame
from rpy2.robjects import default_converter, pandas2ri, numpy2ri
from rpy2.robjects.conversion import localconverter
from rpy2.robjects.packages import importr
import rpy2.robjects.lib.ggplot2 as ggplot2

base = importr('base')
htmlwidgets = importr('htmlwidgets')
ggiraph = importr('ggiraph')
scales = importr('scales')


def htmlwidget(interactive_plot, args):
    knitr_output = htmlwidgets.knit_print_htmlwidget(interactive_plot, standalone=False)
    html = list(knitr_output)[0].replace('<!--html_preserve-->', '').replace('<!--/html_preserve-->', '')
    deps = base.attr(knitr_output, 'knit_meta')
    javascript = ''
    css = ''
    for dep in deps:
        path = Path(list(dep.rx2('src').rx2('file'))[0])
        package = dep.rx2('package')
        if package:
            package_path = Path(base.system_file('', package=package)[0])
            path = package_path / path
        stylesheet = dep.rx2('stylesheet')
        if stylesheet:
            stylesheet = path / list(stylesheet)[0]
            if stylesheet.exists():
                content = stylesheet.read_text()
                css += f'{content}\n'
            else:
                print(f'{stylesheet} does not exist')
        script = dep.rx2('script')

        if script:
            script = path / list(script)[0]
            if script.exists():
                content = script.read_text()
                javascript += f'{content}\n\n'
            else:
                print(f'{script} does not exist')
    style = ''
    for arg in ['width', 'height']:
        value = getattr(args, arg)
        if value is not None:
            style += f'{arg}: {value}px;'
    return (
        f'<div class="girafe-wrapper">'
        f'<style type="text/css">{css}</style>'
        f'<div style="{style}">{html}</div>'
        f'<script type="text/javascript">{javascript}</script>'
        f'</div>'
    )


def register_ggplot_functions(jinja_globals):

    def plot(ggplot_object, width=950, height=480, dpi=100, **kwargs):
        kwargs['width'] = width
        kwargs['height'] = height
        kwargs['dpi'] = dpi
        from markupsafe import Markup

        the_plot = ggiraph.girafe(
            ggobj=ggplot_object,
            options=base.list(
                ggiraph.opts_sizing(width=.7),
                ggiraph.opts_zoom(max=5)
            )
        )

        return Markup(htmlwidget(the_plot, SimpleNamespace(**kwargs)))

    jinja_globals['plot'] = plot

    scales_elements = {
        'format', 'label', 'breaks', 'trans', 'date', 'percent', 'round', 'scientific'
    }
    for key, value in vars(scales).items():
        if key.split('_')[0] in scales_elements:
            jinja_globals[key] = value

    available_elements = {
        'geom', 'stat', 'position', 'theme', 'element', 'scale', 'guide', 'expand',
        'xlim', 'ylim', 'lims', 'ggplot', 'aes', 'annotate', 'arrow', 'annotation',
        'coord', 'facet'
    }
    for key, value in vars(ggplot2).items():
        if key.split('_')[0] in available_elements:
            jinja_globals[key] = value

    for key, value in vars(ggiraph).items():
        if key.split('_')[0] in available_elements:
            jinja_globals[key] = value

    def custom_ggplot(data, mapping=None):
        data = data.infer_objects()
        print(data)
        if len(data) == 0:
            p = ggplot2.ggplot(base.NULL)
        else:
            with localconverter(default_converter + numpy2ri.converter + pandas2ri.converter) as cv:
                r_data = cv.py2rpy(data)

            p = ggplot2.ggplot(r_data)
        if mapping:
            p = p + mapping
        return p

    jinja_globals['ggplot'] = custom_ggplot
