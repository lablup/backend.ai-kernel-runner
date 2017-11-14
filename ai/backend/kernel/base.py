from abc import ABC, abstractmethod
import asyncio
from functools import partial
import json
import logging
import os
from pathlib import Path
import signal
import sys

import aiozmq
# import uvloop
import zmq

from .logging import setup_logger

log = logging.getLogger()


async def pipe_output(stream, outsock, target):
    assert target in ('stdout', 'stderr')
    try:
        while True:
            data = await stream.read(4096)
            if not data:
                break
            outsock.write([target.encode('ascii'), data])
            await outsock.drain()
    except (aiozmq.ZmqStreamClosed, asyncio.CancelledError):
        pass
    except:
        log.exception('unexpected error')


class BaseRunner(ABC):

    log_prefix = 'generic-kernel'

    def __init__(self, loop=None):
        self.child_env = {}
        self.subproc = None

        # initialized after loop creation
        self.loop = loop
        self.insock = None
        self.outsock = None
        self.init_done = None
        self.task_queue = None

        # If the subclass implements interatcive user inputs, it should set a
        # asyncio.Queue-like object to self.user_input_queue in the
        # init_with_loop() method.
        self.user_input_queue = None

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
        try:
            if build_cmd is None or build_cmd == '':
                # skipped
                return
            elif build_cmd == '*':
                if Path('Makefile').is_file():
                    await self.run_subproc('make')
                else:
                    await self.build_heuristic()
            else:
                await self.run_subproc(build_cmd)
        except:
            log.exception('unexpected error')
        finally:
            self.outsock.write([b'build-finished', b''])
            await self.outsock.drain()

    @abstractmethod
    async def build_heuristic(self):
        """Process build step."""

    async def _execute(self, exec_cmd):
        try:
            if exec_cmd is None or exec_cmd == '':
                # skipped
                return
            elif exec_cmd == '*':
                await self.execute_heuristic()
            else:
                await self.run_subproc(exec_cmd)
        except:
            log.exception('unexpected error')
        finally:
            self.outsock.write([b'finished', b''])
            await self.outsock.drain()

    @abstractmethod
    async def execute_heuristic(self):
        """Process execute step."""

    async def _query(self, code_text):
        try:
            return await self.query(code_text)
        except:
            log.exception('unexpected error')
        finally:
            self.outsock.write([b'finished', b''])
            await self.outsock.drain()

    @abstractmethod
    async def query(self, code_text):
        """Run user code by creating a temporary file and compiling it."""

    async def _complete(self, completion_data):
        try:
            return await self.complete(completion_data)
        except:
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
        except:
            log.exception('unexpected error')
        finally:
            # this is a unidirectional command -- no explicit finish!
            await self.outsock.drain()

    @abstractmethod
    async def interrupt(self):
        """Interrupt the running user code (only called for query-mode)."""
        pass

    async def run_subproc(self, cmd):
        """A thin wrapper for an external command."""
        loop = asyncio.get_event_loop()
        try:
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
            await proc.wait()
            await asyncio.gather(*pipe_tasks)
        except:
            log.exception('unexpected error')
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
        except:
            log.exception('unexpected error (handle_user_input)')

    async def run_tasks(self):
        while True:
            try:
                coro = await self.task_queue.get()
                await coro()
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
            except asyncio.CancelledError:
                break
            except NotImplementedError:
                log.error('Unsupported operation for this kernel: {0}', op_type)
                await asyncio.sleep(0)
            except:
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

        def interrupt(loop, stopped):
            if not stopped.is_set():
                stopped.set()
                loop.stop()
            else:
                print('forced shutdown!', file=sys.stderr)
                sys.exit(1)

        loop.add_signal_handler(signal.SIGINT, interrupt, loop, self.stopped)
        loop.add_signal_handler(signal.SIGTERM, interrupt, loop, self.stopped)

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
