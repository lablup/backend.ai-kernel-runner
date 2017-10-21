'''
Displays Agg images in the browser, wrapping them as Sorna media responses.
'''

import base64
import io

# Base imports from matplotlib.backends.backend_template
import matplotlib  # noqa
from matplotlib._pylab_helpers import Gcf
from matplotlib.backend_bases import FigureManagerBase
from matplotlib.figure import Figure

# The real renderer that generates image data
_backend = 'svg'  # noqa
from matplotlib.backends import backend_agg
from matplotlib.backends import backend_svg

# My own imports
from six.moves import builtins

from ..types import MediaRecord


def draw_if_interactive():
    pass


def show():
    for manager in Gcf.get_all_fig_managers():
        manager.show()


def new_figure_manager(num, *args, **kwargs):
    FigureClass = kwargs.pop('FigureClass', Figure)
    thisFig = FigureClass(*args, **kwargs)
    return new_figure_manager_given_figure(num, thisFig)


def new_figure_manager_given_figure(num, figure):
    canvas = FigureCanvas(figure)
    manager = FigureManager(canvas, num)
    return manager


class FigureCanvasSornaAgg(backend_agg.FigureCanvasAgg):
    supports_blit = False

    def __init__(self, *args, **kwargs):
        super(FigureCanvasSornaAgg, self).__init__(*args, **kwargs)
        self._is_old = True
        self._dpi_ratio = 1

    def draw(self):
        renderer = self.get_renderer(cleared=True)
        self._is_old = True
        backend_agg.RendererAgg.lock.acquire()
        try:
            self.figure.draw(renderer)
        finally:
            backend_agg.RendererAgg.lock.release()

    def get_default_filetype(self):
        return 'png'


class FigureCanvasSornaSVG(backend_svg.FigureCanvasSVG):

    def __init__(self, *args, **kwargs):
        super(FigureCanvasSornaSVG, self).__init__(*args, **kwargs)


class FigureManagerSorna(FigureManagerBase):

    def __init__(self, *args, **kwargs):
        super(FigureManagerSorna, self).__init__(*args, **kwargs)

    def show(self):
        if _backend == 'agg':
            with io.BytesIO() as buf:
                self.canvas.print_png(buf)
                raw = buf.getvalue()
            enc = base64.b64encode(raw)
            builtins._sorna_emit(MediaRecord(
                'image/png',
                'data:image/png;base64,' + enc.decode('ascii')
            ))
        elif _backend == 'svg':
            with io.BytesIO() as buf:
                self.canvas.print_svg(buf)
                raw = buf.getvalue()
            builtins._sorna_emit(MediaRecord(
                'image/svg+xml',
                raw.decode('utf8'),
            ))
        else:
            raise RuntimeError('Unsupported sorna matplotlib backend.')


if _backend == 'svg':
    FigureCanvas = FigureCanvasSornaSVG
elif _backend == 'agg':
    FigureCanvas = FigureCanvasSornaAgg
else:
    raise ImportError('_backend has wrong value!')

FigureManager = FigureManagerSorna
