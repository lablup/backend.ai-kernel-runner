import pytest

from six.moves import builtins


@pytest.fixture
def sorna_emit():
    '''
    Returns the reference to a list storing all arguments of each
    builtins._sorna_emit() call.
    '''

    call_args = []

    def _mocked_emit(*args):
        call_args.append(args)

    setattr(builtins, '_sorna_emit', _mocked_emit)

    yield call_args

    delattr(builtins, '_sorna_emit')
