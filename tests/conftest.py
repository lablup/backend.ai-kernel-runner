import os
import subprocess

import pytest
from six.moves import builtins
import zmq, zmq.asyncio

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
def runner_proc(event_loop):
    """ Returns a process which runs kernel runner script and two zmq streams
    for interacting with the runner process.
    """

    zctx = None
    proc = None
    sender = None
    receiver = None

    async def init():
        nonlocal zctx, proc, sender, receiver
        env = os.environ.copy()
        zctx = zmq.asyncio.Context()
        env['LD_PRELOAD'] = ''
        proc = subprocess.Popen(
            'exec python -m ai.backend.kernel --debug c',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            env=env)

        addr = 'tcp://127.0.0.1'
        sender = zctx.socket(zmq.PUSH)
        sender.connect('{}:2000'.format(addr))
        receiver = zctx.socket(zmq.PULL)
        receiver.connect('{}:2001'.format(addr))

    async def shutdown():
        sender.close()
        receiver.close()
        proc.terminate()
        zctx.term()

    event_loop.run_until_complete(init())
    try:
        yield proc, sender, receiver
    finally:
        event_loop.run_until_complete(shutdown())
