import asyncio
import pytest

import aiozmq
import zmq

from ai.backend.kernel.base import pipe_output


@pytest.mark.asyncio
class TestPipeOutput:
    @pytest.fixture
    async def sockets(self, unused_tcp_port):
        addr = f'tcp://127.0.0.1:{unused_tcp_port}'
        outsock = await aiozmq.create_zmq_stream(zmq.PUSH, bind=addr)
        observer = await aiozmq.create_zmq_stream(zmq.PULL, connect=addr)
        return outsock, observer

    async def test_pipe_output_to_stdout(self, sockets):
        proc = await asyncio.create_subprocess_shell(
            'echo stdout...',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        outsock, observer = sockets
        await pipe_output(proc.stdout, outsock, 'stdout')
        await proc.wait()

        type, data = await observer.read()
        assert type.decode('ascii').rstrip() == 'stdout'
        assert data.decode('utf-8').rstrip() == 'stdout...'

    async def test_pipe_output_to_stderr(self, sockets):
        proc = await asyncio.create_subprocess_shell(
            '>&2 echo stderr...',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        outsock, observer = sockets
        await pipe_output(proc.stderr, outsock, 'stderr')
        await proc.wait()

        type, data = await observer.read()
        assert type.decode('ascii').rstrip() == 'stderr'
        assert data.decode('utf-8').rstrip() == 'stderr...'

    async def test_pipe_output_rejects_invalid_target(self, sockets):
        proc = await asyncio.create_subprocess_shell(
            'echo invalid...',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        outsock, observer = sockets

        with pytest.raises(AssertionError):
            await pipe_output(proc.stdout, outsock, 'invalid')
        await proc.wait()

