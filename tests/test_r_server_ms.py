from argparse import Namespace
import asyncio
from datetime import datetime

import pytest

from ai.backend.kernel.r_server_ms import Runner


pytestmark = pytest.mark.asyncio


class DummyOutputSocket:

    def __init__(self):
        self.messages = []

    def write(self, msg):
        self.messages.append(msg)

    async def drain(self):
        pass

    def close(self):
        pass

    def clear(self):
        self.messages.clear()


@pytest.fixture
async def runner(event_loop):
    # Use the environment variables to provide the config for a test setup.
    runner = Runner(loop=event_loop)
    cmdargs = Namespace()
    cmdargs.debug = True

    runner.loop = event_loop
    await runner._init(cmdargs)
    await runner.init_done.wait()

    # mock outsock
    runner.outsock.close()
    runner.outsock = DummyOutputSocket()

    yield runner

    await runner._shutdown()


@pytest.mark.integration
async def test_execute_hello_world(runner):
    await runner.query('cat("hello world")')

    assert 'hello world' in runner.outsock.messages[0][1]


@pytest.mark.integration
async def test_refresh_token(runner):
    first_token = None
    second_token = None

    await runner.query('cat("first world")')
    first_token = runner.access_token
    runner.expires_on = datetime.now()
    await asyncio.sleep(0.1)
    await runner.query('cat("second world")')
    second_token = runner.access_token

    assert first_token != second_token  # refreshed!
    assert 'first world' in runner.outsock.messages[0][1]
    assert 'second world' in runner.outsock.messages[1][1]
