import pytest

from six.moves import builtins

from ai.backend.kernel.base import BaseRunner


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


@pytest.fixture
def base_runner():
    """ Return a concrete object of abstract BaseRunner for testing."""
    def concreter(abclass):
        class concreteCls(abclass):
            pass
        concreteCls.__abstractmethods__ = frozenset()
        return type('DummyConcrete' + abclass.__name__, (concreteCls,), {})

    return concreter(BaseRunner)()
