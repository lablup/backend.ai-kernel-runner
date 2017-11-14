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
    runner = Runner(endpoint='', credentials={
        'username': '',
        'password': '',
    })
    loop = asyncio.get_event_loop()
    runner.loop = loop
    runner.outsock = DummyOutputSocket()

    cmdargs = Namespace()
    cmdargs.debug = True

    try:
        runner.task_queue = asyncio.Queue(loop=loop)
        run_task = loop.create_task(runner.run_tasks())
        main_task = loop.create_task(runner.main_loop(cmdargs))

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
@pytest.mark.asyncio
async def test_execute(runner):
    await runner.query('cat("hello world")')
    print(runner.outsock.messages)
