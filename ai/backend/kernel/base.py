from abc import ABC, abstractmethod
import asyncio
from functools import partial
import json
import logging
import os
from pathlib import Path
import signal
import sys
import time

import aiozmq
import msgpack
# import uvloop
import zmq

from .logging import setup_logger

log = logging.getLogger()


async def pipe_output(stream, outsock, target):
    assert target in ('stdout', 'stderr')
    target = target.encode('ascii')
    fd = sys.stdout.fileno() if target == 'stdout' else sys.stderr.fileno()
    try:
        while True:
            data = await stream.read(4096)
            if not data:
                break
            os.write(fd, data)
            outsock.write([target, data])
            await outsock.drain()
    except (aiozmq.ZmqStreamClosed, asyncio.CancelledError):
        pass
    except Exception:
        log.exception('unexpected error')


class BaseRunner(ABC):

    log_prefix = 'generic-kernel'

    def __init__(self, loop=None):
        self.child_env = {}
        self.subproc = None

        work_dir = Path(os.getcwd())
        config_dir = work_dir / '.config'
        try:
            evdata = (config_dir / 'environ.txt').read_text()
            for line in evdata.splitlines():
                k, v = line.split('=', 1)
                self.child_env[k] = v
        except FileNotFoundError:
            pass
        except Exception:
            log.exception('Reading .config/environ.txt failed!')

        # initialized after loop creation
        self.loop = loop
        self.started_at: float = time.monotonic()
        self.insock = None
        self.outsock = None
        self.init_done = None
        self.task_queue = None

        # If the subclass implements interatcive user inputs, it should set a
        # asyncio.Queue-like object to self.user_input_queue in the
        # init_with_loop() method.
        self.user_input_queue = None

        # build status tracker to skip the execute step
        self._build_success = None

    async def _init_with_loop(self):
        if self.init_done is not None:
            self.init_done.clear()
        try:
            await self.init_with_loop()
        except Exception:
            log.exception('unexpected error')
            return
        if self.init_done is not None:
            self.init_done.set()

    @abstractmethod
    async def init_with_loop(self):
        """Initialize after the event loop is created."""

    async def _build(self, build_cmd):
        ret = 0
        try:
            if build_cmd is None or build_cmd == '':
                # skipped
                return
            elif build_cmd == '*':
                if Path('Makefile').is_file():
                    ret = await self.run_subproc('make')
                else:
                    ret = await self.build_heuristic()
            else:
                ret = await self.run_subproc(build_cmd)
        except Exception:
            log.exception('unexpected error')
            ret = -1
        finally:
            self._build_success = (ret == 0)
            payload = json.dumps({
                'exitCode': ret,
            }).encode('utf8')
            self.outsock.write([b'build-finished', payload])
            await self.outsock.drain()

    @abstractmethod
    async def build_heuristic(self) -> int:
        """Process build step."""

    async def _execute(self, exec_cmd):
        ret = 0
        try:
            if exec_cmd is None or exec_cmd == '':
                # skipped
                return
            elif exec_cmd == '*':
                ret = await self.execute_heuristic()
            else:
                ret = await self.run_subproc(exec_cmd)
        except Exception:
            log.exception('unexpected error')
            ret = -1
        finally:
            payload = json.dumps({
                'exitCode': ret,
            }).encode('utf8')
            self.outsock.write([b'finished', payload])
            await self.outsock.drain()

    @abstractmethod
    async def execute_heuristic(self) -> int:
        """Process execute step."""

    async def _query(self, code_text):
        ret = 0
        try:
            ret = await self.query(code_text)
        except Exception:
            log.exception('unexpected error')
            ret = -1
        finally:
            payload = json.dumps({
                'exitCode': ret,
            }).encode('utf8')
            self.outsock.write([b'finished', payload])
            await self.outsock.drain()

    @abstractmethod
    async def query(self, code_text) -> int:
        """Run user code by creating a temporary file and compiling it."""

    async def _complete(self, completion_data):
        try:
            return await self.complete(completion_data)
        except Exception:
            log.exception('unexpected error')
        finally:
            pass  # no need to "finished" signal

    @abstractmethod
    async def complete(self, completion_data):
        """Return the list of strings to be shown in the auto-complete list."""

    async def _interrupt(self):
        try:
            if self.subproc:
                self.subproc.send_signal(signal.SIGINT)
                return
            return await self.interrupt()
        except Exception:
            log.exception('unexpected error')
        finally:
            # this is a unidirectional command -- no explicit finish!
            await self.outsock.drain()

    @abstractmethod
    async def interrupt(self):
        """Interrupt the running user code (only called for query-mode)."""
        pass

    async def _send_status(self):
        data = {
            'started_at': self.started_at,
        }
        self.outsock.write([
            b'status',
            msgpack.packb(data, use_bin_type=True),
        ])
        await self.outsock.drain()

    async def run_subproc(self, cmd):
        """A thin wrapper for an external command."""
        loop = asyncio.get_event_loop()
        try:
            # errors like "command not found" is handled by the spawned shell.
            # (the subproc will terminate immediately with return code 127)
            proc = await asyncio.create_subprocess_shell(
                cmd,
                env=self.child_env,
                stdin=None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            self.subproc = proc
            pipe_tasks = [
                loop.create_task(pipe_output(proc.stdout, self.outsock, 'stdout')),
                loop.create_task(pipe_output(proc.stderr, self.outsock, 'stderr')),
            ]
            retcode = await proc.wait()
            await asyncio.gather(*pipe_tasks)
            return retcode
        except Exception:
            log.exception('unexpected error')
            return -1
        finally:
            self.subproc = None

    async def shutdown(self):
        pass

    async def handle_user_input(self, reader, writer):
        try:
            if self.user_input_queue is None:
                writer.write(b'<user-input is unsupported>')
            else:
                self.outsock.write([b'waiting-input', b''])
                text = await self.user_input_queue.get()
                writer.write(text.encode('utf8'))
            await writer.drain()
            writer.close()
        except Exception:
            log.exception('unexpected error (handle_user_input)')

    async def run_tasks(self):
        while True:
            try:
                coro = await self.task_queue.get()

                if (self._build_success is not None and
                        coro.func == self._execute and
                        not self._build_success):
                    self._build_success = None
                    # skip exec step with "command not found" exit code
                    payload = json.dumps({
                        'exitCode': 127,
                    }).encode('utf8')
                    self.outsock.write([b'finished', payload])
                    await self.outsock.drain()
                    self.task_queue.task_done()
                    continue

                await coro()
                self.task_queue.task_done()
            except asyncio.CancelledError:
                break

    async def main_loop(self, cmdargs):
        self.insock = await aiozmq.create_zmq_stream(zmq.PULL,
                                                     bind='tcp://*:2000')
        self.outsock = await aiozmq.create_zmq_stream(zmq.PUSH,
                                                      bind='tcp://*:2001')
        user_input_server = \
            await asyncio.start_server(self.handle_user_input,
                                       '127.0.0.1', 65000)
        setup_logger(self.outsock, self.log_prefix, cmdargs.debug)

        await self._init_with_loop()
        log.debug('start serving...')
        while True:
            try:
                data = await self.insock.read()
                op_type = data[0].decode('ascii')
                text = data[1].decode('utf8')
                if op_type == 'build':    # batch-mode step 1
                    await self.task_queue.put(partial(self._build, text))
                elif op_type == 'exec':   # batch-mode step 2
                    await self.task_queue.put(partial(self._execute, text))
                elif op_type == 'code':   # query-mode
                    await self.task_queue.put(partial(self._query, text))
                elif op_type == 'input':  # interactive input
                    if self.user_input_queue is not None:
                        await self.user_input_queue.put(text)
                elif op_type == 'complete':  # auto-completion
                    data = json.loads(text)
                    await self._complete(data)
                elif op_type == 'interrupt':
                    await self._interrupt()
                elif op_type == 'status':
                    await self._send_status()
            except asyncio.CancelledError:
                break
            except NotImplementedError:
                log.error('Unsupported operation for this kernel: {0}', op_type)
                await asyncio.sleep(0)
            except Exception:
                log.exception('unexpected error')
                break
        user_input_server.close()
        await user_input_server.wait_closed()
        await self.shutdown()
        self.insock.close()

    async def _init(self, cmdargs):
        self.task_queue = asyncio.Queue(loop=self.loop)
        self.init_done = asyncio.Event(loop=self.loop)
        self._main_task = self.loop.create_task(self.main_loop(cmdargs))
        self._run_task = self.loop.create_task(self.run_tasks())

    async def _shutdown(self):
        self._run_task.cancel()
        self._main_task.cancel()
        await self._run_task
        await self._main_task

    def run(self, cmdargs):
        # Replace stdin with a "null" file
        # (trying to read stdin will raise EOFError immediately afterwards.)
        sys.stdin = open(os.devnull, 'rb')

        # Initialize event loop.
        # TODO: fix use of uvloop (#2)
        # asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        loop = asyncio.get_event_loop()
        self.loop = loop
        self.stopped = asyncio.Event(loop=loop)

        def terminate(loop, stopped):
            if not stopped.is_set():
                stopped.set()
                loop.stop()
            else:
                print('forced shutdown!', file=sys.stderr)
                sys.exit(1)

        loop.add_signal_handler(signal.SIGINT, terminate, loop, self.stopped)
        loop.add_signal_handler(signal.SIGTERM, terminate, loop, self.stopped)

        try:
            loop.run_until_complete(self._init(cmdargs))
            loop.run_forever()
            # interrupted
            loop.run_until_complete(self._shutdown())
        finally:
            log.debug('exit.')
            # This should be preserved as long as possible for logging
            if self.outsock:
                self.outsock.close()
            loop.close()
