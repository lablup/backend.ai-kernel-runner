import asyncio
import logging
import os
from pathlib import Path
import shlex
import tempfile

from .. import BaseRunner

log = logging.getLogger()

DEFAULT_CFLAGS = '-Wall'
DEFAULT_LDFLAGS = '-lrt -lm -pthread -ldl'
CHILD_ENV = {
    'TERM': 'xterm',
    'LANG': 'C.UTF-8',
    'SHELL': '/bin/ash',
    'USER': 'work',
    'HOME': '/home/work',
    'PATH': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
    'LD_PRELOAD': os.environ.get('LD_PRELOAD', '/home/sorna/patch-libs.so'),
}


class Runner(BaseRunner):

    log_prefix = 'c-kernel'

    def __init__(self):
        super().__init__()
        self.child_env.update(CHILD_ENV)

    async def init_with_loop(self):
        self.user_input_queue = asyncio.Queue()

    async def build_heuristic(self):
        if Path('main.c').is_file():
            cfiles = list(Path('.').glob('**/*.c'))
            ofiles = [Path(p.stem + '.o') for p in cfiles]
            for cf in cfiles:
                cmd = f'gcc -c {cf} {DEFAULT_CFLAGS}'
                await self.run_subproc(cmd)
            cfiles = ' '.join(map(lambda p: shlex.quote(str(p)), cfiles))
            ofiles = ' '.join(map(lambda p: shlex.quote(str(p)), ofiles))
            cmd = f'gcc {ofiles} {DEFAULT_LDFLAGS} -o ./main'
            await self.run_subproc(cmd)
        else:
            log.error('cannot find build script ("Makefile") '
                      'or the main file ("main.c").')

    async def execute_heuristic(self):
        if Path('./main').is_file():
            await self.run_subproc('./main')
        elif Path('./a.out').is_file():
            await self.run_subproc('./a.out')
        else:
            log.error('cannot find executable ("a.out" or "main").')

    async def query(self, code_text):
        with tempfile.NamedTemporaryFile(suffix='.c', dir='.') as tmpf:
            tmpf.write(code_text.encode('utf8'))
            tmpf.flush()
            cmd = (
                f'gcc {tmpf.name} {DEFAULT_CFLAGS} -o ./main {DEFAULT_LDFLAGS} && '
                f'./main')
            await self.run_subproc(cmd)

    async def complete(self, data):
        return []

    async def interrupt(self):
        # subproc interrupt is already handled by BaseRunner
        pass
