import asyncio
import signal
import subprocess
import time

import aiozmq
import asynctest
import pytest
import zmq

from ai.backend.kernel.base import pipe_output


@pytest.mark.asyncio
class TestPipeOutput:
    @pytest.fixture
    async def sockets(self, unused_tcp_port):
        addr = f'tcp://127.0.0.1:{unused_tcp_port}'
        outsock = await aiozmq.create_zmq_stream(zmq.PUSH, bind=addr)
        observer = await aiozmq.create_zmq_stream(zmq.PULL, connect=addr)
        yield outsock, observer
        outsock.close()
        observer.close()

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


class TestBaseRunner:
    @pytest.fixture
    async def sockets(self):
        addr = f'tcp://127.0.0.1'
        sender = await aiozmq.create_zmq_stream(zmq.PUSH,
                                                connect=f'{addr}:2000')
        receiver = await aiozmq.create_zmq_stream(zmq.PULL,
                                                  connect=f'{addr}:2001')
        yield sender, receiver
        sender.close()
        receiver.close()

    @pytest.mark.asyncio
    async def test_skip_build_without_cmd(self, base_runner):
        base_runner.run_subproc = asynctest.CoroutineMock()
        base_runner.build_heuristic = asynctest.CoroutineMock()
        base_runner.outsock = asynctest.Mock(spec=aiozmq.ZmqStream)

        await base_runner._build(None)
        await base_runner._build('')

        base_runner.run_subproc.assert_not_called()
        base_runner.build_heuristic.assert_not_called()

    @pytest.mark.asyncio
    async def test_build_cmd_execution(self, runner_proc):
        proc, sender, receiver = runner_proc

        sender.write([b'build', b'echo testing...'])
        op_type, data = await receiver.read()
        assert op_type.decode('ascii').rstrip() == 'stdout'
        assert data.decode('utf-8').rstrip() == 'testing...'

    @pytest.mark.asyncio
    async def test_execution_build_without_cmd(self, base_runner):
        base_runner.run_subproc = asynctest.CoroutineMock()
        base_runner.build_heuristic = asynctest.CoroutineMock()
        base_runner.outsock = asynctest.Mock(spec=aiozmq.ZmqStream)

        await base_runner._execute(None)
        await base_runner._execute('')

        base_runner.run_subproc.assert_not_called()
        base_runner.build_heuristic.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_cmd_execution(self, runner_proc):
        proc, sender, receiver = runner_proc

        sender.write([b'exec', b'echo testing...'])
        op_type, data = await receiver.read()
        assert op_type.decode('ascii').rstrip() == 'stdout'
        assert data.decode('utf-8').rstrip() == 'testing...'

    @pytest.mark.parametrize('sig', [signal.SIGINT, signal.SIGTERM])
    def test_interruption(self, runner_proc, sig):
        proc, sender, receiver = runner_proc

        time.sleep(1)  # wait for runner initialization
        proc.send_signal(sig)
        try:
            stdout, stderr = proc.communicate(2)
        except subprocess.TimeoutExpired:
            pass
        assert b'exit' in stderr or b'exit' in stdout

    @pytest.mark.asyncio
    async def test_run_subproc(self, base_runner):
        addr = 'tcp://127.0.0.1:2001'
        base_runner.outsock = await aiozmq.create_zmq_stream(zmq.PUSH,
                                                             bind=addr)
        observer = await aiozmq.create_zmq_stream(zmq.PULL, connect=addr)

        await base_runner.run_subproc('echo testing...')
        op_type, data = await observer.read()
        assert op_type.decode('ascii').rstrip() == 'stdout'
        assert data.decode('utf-8').rstrip() == 'testing...'

        base_runner.outsock.close()
        observer.close()

    def test_run_tasks(self, base_runner, event_loop):
        async def fake_task():
            base_runner.task_done = True
            raise asyncio.CancelledError

        async def insert_task_to_queue():
            await base_runner.task_queue.put(fake_task)

        base_runner.task_queue = asyncio.Queue(loop=event_loop)
        base_runner.task_done = False
        tasks = [base_runner.run_tasks(), insert_task_to_queue()]
        event_loop.run_until_complete(asyncio.wait(tasks))

        assert base_runner.task_done
