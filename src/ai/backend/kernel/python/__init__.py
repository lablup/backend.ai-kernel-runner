import asyncio
import ctypes
import json
import logging
import os
from pathlib import Path
import shutil
import site
import tempfile
import threading

import janus

from .. import BaseRunner
from .inproc import PythonInprocRunner

log = logging.getLogger()

DEFAULT_PYFLAGS = ''
CHILD_ENV = {
    'TERM': 'xterm',
    'LANG': 'C.UTF-8',
    'SHELL': '/bin/ash' if Path('/bin/ash').is_file() else '/bin/bash',
    'USER': 'work',
    'HOME': '/home/work',
    'PATH': ':'.join([
        '/usr/local/nvidia/bin',
        '/usr/local/cuda/bin',
        '/usr/local/sbin',
        '/usr/local/bin',
        '/usr/sbin',
        '/usr/bin',
        '/sbin',
        '/bin',
    ]),
    'LD_LIBRARY_PATH': os.environ.get('LD_LIBRARY_PATH', ''),
    'LD_PRELOAD': '/home/backend.ai/libbaihook.so',
}


class Runner(BaseRunner):

    log_prefix = 'python-kernel'

    def __init__(self):
        super().__init__()
        self.child_env.update(CHILD_ENV)
        self.inproc_runner = None
        self.sentinel = object()
        self.input_queue = None
        self.output_queue = None

        # Add sitecustomize.py to site-packages directory.
        # No permission to access global site packages, we use user local directory.
        input_src = Path(os.path.dirname(__file__)) / 'sitecustomize.py'
        # pkgdir = Path(site.getsitepackages()[0])
        pkgdir = Path(site.USER_SITE)
        pkgdir.mkdir(parents=True, exist_ok=True)
        shutil.copy(str(input_src), str(pkgdir / 'sitecustomize.py'))

    async def init_with_loop(self):
        self.input_queue = janus.Queue(loop=self.loop)
        self.output_queue = janus.Queue(loop=self.loop)

        # We have interactive input functionality!
        self._user_input_queue = janus.Queue(loop=self.loop)
        self.user_input_queue = self._user_input_queue.async_q

    async def build_heuristic(self) -> int:
        if Path('setup.py').is_file():
            cmd = f'python {DEFAULT_PYFLAGS} setup.py develop'
            return await self.run_subproc(cmd)
        else:
            log.warning('skipping the build phase due to missing "setup.py" file')
            return 0

    async def execute_heuristic(self) -> int:
        if Path('main.py').is_file():
            cmd = f'python {DEFAULT_PYFLAGS} main.py'
            return await self.run_subproc(cmd)
        else:
            log.error('cannot find the main script ("main.py").')
            return 127

    async def query(self, code_text) -> int:
        self.ensure_inproc_runner()
        await self.input_queue.async_q.put(code_text)
        # Read the generated outputs until done
        while True:
            try:
                msg = await self.output_queue.async_q.get()
            except asyncio.CancelledError:
                break
            self.output_queue.async_q.task_done()
            if msg is self.sentinel:
                break
            self.outsock.send_multipart(msg)
        return 0

    async def complete(self, data):
        self.ensure_inproc_runner()
        matches = self.inproc_runner.complete(data)
        self.outsock.send_multipart([
            b'completion',
            json.dumps(matches).encode('utf8'),
        ])

    async def interrupt(self):
        if self.inproc_runner is None:
            log.error('No user code is running!')
            return
        # A dirty hack to raise an exception inside a running thread.
        target_tid = self.inproc_runner.ident
        if target_tid not in {t.ident for t in threading.enumerate()}:
            log.error('Interrupt failed due to missing thread.')
            return
        affected_count = ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_long(target_tid),
            ctypes.py_object(KeyboardInterrupt))
        if affected_count == 0:
            log.error('Interrupt failed due to invalid thread identity.')
        elif affected_count > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_long(target_tid),
                ctypes.c_long(0))
            log.error('Interrupt broke the interpreter state -- '
                      'recommended to reset the session.')

    async def start_service(self, service_info):
        if service_info['name'] == 'jupyter':
            with tempfile.NamedTemporaryFile(
                    'w', encoding='utf-8', suffix='.py', delete=False) as config:
                print('c.NotebookApp.allow_root = True', file=config)
                print('c.NotebookApp.ip = "0.0.0.0"', file=config)
                print('c.NotebookApp.port = {}'.format(service_info['port']),
                      file=config)
                print('c.NotebookApp.token = ""', file=config)
            return [
                '/usr/local/bin/python',
                '-m', 'jupyter', 'notebook',
                '--no-browser',
                '--config',
                config.name,
            ], {}
        elif service_info['name'] == 'ipython':
            return [
                '/usr/local/bin/python',
                '-m', 'ipython',
            ], {}

    def ensure_inproc_runner(self):
        if self.inproc_runner is None:
            self.inproc_runner = PythonInprocRunner(
                self.input_queue.sync_q,
                self.output_queue.sync_q,
                self._user_input_queue.sync_q,
                self.sentinel)
            self.inproc_runner.start()
