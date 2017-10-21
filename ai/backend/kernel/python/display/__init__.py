'''
This module is an equivalent of IPython.display module.
'''

from six.moves import builtins
import pandas as pd
import numpy as np

from ..types import (
    MediaRecord, HTMLRecord
)

__all__ = (
    'MediaRecord', 'HTMLRecord', 'display',
)


def display(obj, **kwargs):
    if isinstance(obj, pd.DataFrame):
        builtins._sorna_emit(HTMLRecord(obj.to_html()))
        return
    if isinstance(obj, np.ndarray):
        df = pd.DataFrame(obj, **kwargs)
        builtins._sorna_emit(HTMLRecord(df.to_html()))
        return
    raise TypeError('Unsupported object type for display.')
