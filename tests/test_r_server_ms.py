from argparse import Namespace
import asyncio
import os
import signal

import pytest

from ai.backend.kernel.r_server_ms import Runner


class DummyOutputSocket:

    def __init__(self):
        self.messages = []

    def write(self, msg):
        self.messages.append(msg)

    def clear(self):
        self.messages.clear()


@pytest.fixture
def runner():
    # Use the environment variables to provide the config for a test setup.
    runner = Runner()
    loop = asyncio.get_event_loop()
    runner.loop = loop

    cmdargs = Namespace()
    cmdargs.debug = True

    try:
        runner.task_queue = asyncio.Queue(loop=loop)
        run_task = loop.create_task(runner.run_tasks())
        main_task = loop.create_task(runner.main_loop(cmdargs))

        loop.run_until_complete(runner.init_done.wait())

        # mock
        runner.outsock = DummyOutputSocket()

        yield runner

        run_task.cancel()
        main_task.cancel()
        try:
            loop.run_until_complete(run_task)
        except asyncio.CancelledError:
            pass
        try:
            loop.run_until_complete(main_task)
        except asyncio.CancelledError:
            pass
    finally:
        loop.close()


@pytest.mark.integration
def test_execute_hello_world(runner):

    async def do():
        await runner.query('cat("hello world")')

    # need to wrap in a task for aiohttp
    task = runner.loop.create_task(do())
    runner.loop.run_until_complete(task)

    print(runner.outsock.messages)
    assert 'hello world' in runner.outsock.messages[0][1]
