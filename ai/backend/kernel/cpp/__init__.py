import logging
import os
from pathlib import Path
import shlex
import tempfile

from .. import BaseRunner

log = logging.getLogger()

DEFAULT_CFLAGS = '-Wall'
DEFAULT_LDFLAGS = '-lrt -lm -pthread'
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

    log_prefix = 'cpp-kernel'

    def __init__(self):
        super().__init__()
        self.child_env.update(CHILD_ENV)

    async def init_with_loop(self):
        pass

    async def build_heuristic(self):
        if Path('main.cpp').is_file():
            cppfiles = Path('.').glob('**/*.cpp')
            cppfiles = ' '.join(map(lambda p: shlex.quote(str(p)), cppfiles))
            cmd = (
                f'g++ {cppfiles} {DEFAULT_CFLAGS} -o ./main {DEFAULT_LDFLAGS};'
                f'./main'
            )
            await self.run_subproc(cmd)
        else:
            log.error('cannot find build script ("Makefile") '
                      'or the main file ("main.cpp").')

    async def execute_heuristic(self):
        if Path('./main').is_file():
            await self.run_subproc('./main')
        elif Path('./a.out').is_file():
            await self.run_subproc('./a.out')
        else:
            log.error('cannot find executable ("a.out" or "main").')

    async def query(self, code_text):
        with tempfile.NamedTemporaryFile(suffix='.cpp', dir='.') as tmpf:
            tmpf.write(code_text.encode('utf8'))
            tmpf.flush()
            cmd = (
                f'g++ {tmpf.name} {DEFAULT_CFLAGS} -o ./main {DEFAULT_LDFLAGS}'
                f'&& ./main'
            )
            await self.run_subproc(cmd)

    async def complete(self, data):
        return []

    async def interrupt(self):
        # subproc interrupt is already handled by BaseRunner
        pass
