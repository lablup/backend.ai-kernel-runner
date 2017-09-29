import pytest

import matplotlib
matplotlib.use('module://ai.backend.kernel.python.matplotlib.ingen')
import matplotlib.pyplot as plt
from six.moves import builtins

from ai.backend.kernel.python.matplotlib import ingen


def test_matplotlib_backend_replaced(sorna_emit):
    ingen.FigureCanvas = ingen.FigureCanvasSornaAgg
    ingen._backend = 'agg'
    sorna_emit.clear()
    plt.plot([1, 2, 3, 4])
    plt.ylabel('some numbers')
    plt.show()
    plt.close()
    assert len(sorna_emit) > 0
    assert sorna_emit[0][0].type == 'image/png'

    ingen.FigureCanvas = ingen.FigureCanvasSornaSVG
    ingen._backend = 'svg'
    sorna_emit.clear()
    plt.plot([1, 2, 3, 4])
    plt.ylabel('some numbers')
    plt.show()
    plt.close()
    assert len(sorna_emit) > 0
    assert sorna_emit[0][0].type == 'image/svg+xml'
