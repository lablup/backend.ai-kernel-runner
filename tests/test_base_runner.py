import asyncio
import json
import signal
import time
from unittest.mock import call

import asynctest
import pytest
import zmq, zmq.asyncio

from ai.backend.kernel.base import pipe_output
from ai.backend.kernel.test_utils import MockableZMQAsyncSock


@pytest.fixture
async def sockets(unused_tcp_port):
    zctx = zmq.asyncio.Context()
    addr = f'tcp://127.0.0.1:{unused_tcp_port}'
    outsock = zctx.socket(zmq.PUSH)
    outsock.bind(addr)
    observer = zctx.socket(zmq.PULL)
    observer.connect(addr)
    yield outsock, observer
    outsock.close()
    observer.close()
    zctx.term()


class TestPipeOutput:

    @pytest.mark.asyncio
    async def test_pipe_output_to_stdout(self, sockets):
        proc = await asyncio.create_subprocess_shell(
            'echo stdout...',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        outsock, observer = sockets
        await pipe_output(proc.stdout, outsock, 'stdout')
        await proc.wait()

        type, data = await observer.recv_multipart()
        assert type.decode('ascii').rstrip() == 'stdout'
        assert data.decode('utf-8').rstrip() == 'stdout...'

    @pytest.mark.asyncio
    async def test_pipe_output_to_stderr(self, sockets):
        proc = await asyncio.create_subprocess_shell(
            '>&2 echo stderr...',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        outsock, observer = sockets
        await pipe_output(proc.stderr, outsock, 'stderr')
        await proc.wait()

        type, data = await observer.recv_multipart()
        assert type.decode('ascii').rstrip() == 'stderr'
        assert data.decode('utf-8').rstrip() == 'stderr...'

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
    async def test_skip_clean_without_cmd(self, base_runner):
        base_runner.run_subproc = asynctest.CoroutineMock()
        base_runner.build_heuristic = asynctest.CoroutineMock()
        base_runner.outsock = MockableZMQAsyncSock.create_mock()

        await base_runner._clean(None)
        await base_runner._clean('')

        base_runner.run_subproc.assert_not_called()
        base_runner.build_heuristic.assert_not_called()

    @pytest.mark.asyncio
    async def test_clean_cmd_execution(self, runner_proc):
        proc, sender, receiver = runner_proc
        await sender.send_multipart([b'clean', b'echo testing...'])
        records = []
        exit_code = None
        while True:
            op_type, data = await receiver.recv_multipart()
            records.append((op_type, data))
            if op_type == b'clean-finished':
                exit_code = json.loads(data)['exitCode']
                break
        assert exit_code == 0
        assert records[0][0].decode('ascii').rstrip() == 'stdout'
        assert records[0][1].decode('utf-8').rstrip() == 'testing...'

    @pytest.mark.asyncio
    async def test_clean_cmd_failure(self, runner_proc):
        proc, sender, receiver = runner_proc
        await sender.send_multipart([b'clean', b'exit 1'])
        exit_code = None
        while True:
            op_type, data = await receiver.recv_multipart()
            if op_type == b'clean-finished':
                exit_code = json.loads(data)['exitCode']
                break
        assert exit_code == 1

    @pytest.mark.asyncio
    async def test_skip_build_without_cmd(self, base_runner):
        base_runner.run_subproc = asynctest.CoroutineMock()
        base_runner.build_heuristic = asynctest.CoroutineMock()
        base_runner.outsock = MockableZMQAsyncSock.create_mock()

        await base_runner._build(None)
        await base_runner._build('')

        base_runner.run_subproc.assert_not_called()
        base_runner.build_heuristic.assert_not_called()

    @pytest.mark.asyncio
    async def test_build_cmd_execution(self, runner_proc):
        proc, sender, receiver = runner_proc
        await sender.send_multipart([b'build', b'echo testing...'])
        records = []
        exit_code = None
        while True:
            op_type, data = await receiver.recv_multipart()
            records.append((op_type, data))
            if op_type == b'build-finished':
                exit_code = json.loads(data)['exitCode']
                break
        assert exit_code == 0
        assert records[0][0].decode('ascii').rstrip() == 'stdout'
        assert records[0][1].decode('utf-8').rstrip() == 'testing...'

    @pytest.mark.asyncio
    async def test_build_cmd_failure(self, runner_proc):
        proc, sender, receiver = runner_proc
        await sender.send_multipart([b'build', b'exit 99'])
        exit_code = None
        while True:
            op_type, data = await receiver.recv_multipart()
            if op_type == b'build-finished':
                exit_code = json.loads(data)['exitCode']
                break
        assert exit_code == 99

    @pytest.mark.asyncio
    async def test_skip_execute_without_cmd(self, base_runner):
        base_runner.run_subproc = asynctest.CoroutineMock()
        base_runner.build_heuristic = asynctest.CoroutineMock()
        base_runner.outsock = MockableZMQAsyncSock.create_mock()

        await base_runner._execute(None)
        await base_runner._execute('')

        base_runner.run_subproc.assert_not_called()
        base_runner.build_heuristic.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_cmd_execution(self, runner_proc):
        proc, sender, receiver = runner_proc
        await sender.send_multipart([b'exec', b'echo testing...'])
        records = []
        exit_code = None
        while True:
            op_type, data = await receiver.recv_multipart()
            records.append((op_type, data))
            if op_type == b'finished':
                exit_code = json.loads(data)['exitCode']
                break
        assert exit_code == 0
        assert records[0][0].decode('ascii').rstrip() == 'stdout'
        assert records[0][1].decode('utf-8').rstrip() == 'testing...'

    @pytest.mark.asyncio
    async def test_execute_cmd_failure(self, runner_proc):
        proc, sender, receiver = runner_proc
        await sender.send_multipart([b'exec', b'./non-existent-executable'])
        exit_code = None
        while True:
            op_type, data = await receiver.recv_multipart()
            if op_type == b'finished':
                exit_code = json.loads(data)['exitCode']
                break
        assert exit_code == 127

    @pytest.mark.asyncio
    async def test_execute_cmd_skip_if_build_failed(self, runner_proc):
        proc, sender, receiver = runner_proc
        await sender.send_multipart([b'build', b'exit 1'])
        await sender.send_multipart([b'exec', b'echo hello'])
        records = []
        build_exit_code = None
        exec_exit_code = None
        while True:
            op_type, data = await receiver.recv_multipart()
            if op_type == b'build-finished':
                build_exit_code = json.loads(data)['exitCode']
            elif op_type == b'finished':
                exec_exit_code = json.loads(data)['exitCode']
                break
            elif op_type == b'stdout':
                records.append(data)
        assert build_exit_code == 1
        assert exec_exit_code == 127
        assert len(records) == 0  # should not have printed anything

    @pytest.mark.parametrize('sig', [signal.SIGINT, signal.SIGTERM])
    def test_interruption(self, runner_proc, sig):
        proc, sender, receiver = runner_proc
        time.sleep(0.3)  # wait for runner initialization

        def alarmed(signum, frame):
            signal.alarm(0)
            proc.send_signal(sig)

        signal.signal(signal.SIGALRM, alarmed)
        signal.setitimer(signal.ITIMER_REAL, 0.2)

        proc.wait()
        assert b'exit' in proc.stderr.read()

    @pytest.mark.asyncio
    async def test_run_subproc(self, base_runner):
        base_runner.outsock = MockableZMQAsyncSock.create_mock()
        await base_runner.run_subproc('echo testing...')

        base_runner.outsock.send_multipart.assert_has_awaits([
            call([b'stdout', b'testing...\n']),
        ], any_order=True)

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
