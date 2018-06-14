from six.moves import builtins

__all__ = (
    'display',
)


def display(obj, **kwargs):
    # Perform lazy-import for fast initialization.
    # Note: pd/np are likely to be already imported by user codes!
    import pandas as pd
    import numpy as np
    if isinstance(obj, pd.DataFrame):
        r = (b'html', obj.to_html().encode('utf8'))
        builtins._sorna_emit(r)
        return
    if isinstance(obj, np.ndarray):
        df = pd.DataFrame(obj, **kwargs)
        r = (b'html', df.to_html().encode('utf8'))
        builtins._sorna_emit(r)
        return
    raise TypeError('Unsupported object type for display.')
