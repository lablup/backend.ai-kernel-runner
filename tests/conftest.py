import os
import subprocess

import aiozmq
import pytest
from six.moves import builtins
import zmq

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


@pytest.fixture
async def runner_proc():
    """ Returns a process which runs kernel runner script and two zmq streams
    for interacting with the runner process.
    """
    env = os.environ.copy()
    env['LD_PRELOAD'] = ''
    proc = subprocess.Popen(
        'python -m ai.backend.kernel --debug c',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        env=env)

    addr = f'tcp://127.0.0.1'
    sender = await aiozmq.create_zmq_stream(zmq.PUSH, connect=f'{addr}:2000')
    receiver = await aiozmq.create_zmq_stream(zmq.PULL, connect=f'{addr}:2001')

    yield proc, sender, receiver

    sender.close()
    receiver.close()
    proc.terminate()
