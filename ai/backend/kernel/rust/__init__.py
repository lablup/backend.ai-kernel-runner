import logging
import os
from pathlib import Path
import tempfile

from .. import BaseRunner
from ..utils import find_executable

log = logging.getLogger()

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

    log_prefix = 'rust-kernel'

    def __init__(self):
        super().__init__()
        self.child_env.update(CHILD_ENV)

    async def init_with_loop(self):
        pass

    async def build_heuristic(self):
        if Path('Cargo.toml').is_file():
            await self.run_subproc('cargo build')
        elif Path('main.rs').is_file():
            await self.run_subproc('rustc -o main main.rs')
        else:
            log.error(
                'cannot find the main/build file ("Cargo.toml" or "main.rs").')

    async def execute_heuristic(self):
        out = find_executable('./target/debug', './target/release')
        if out is not None:
            await self.run_subproc(f'{out}')
        elif Path('./main').is_file():
            await self.run_subproc('./main')
        else:
            log.error('cannot find executable ("main" or target directories).')

    async def query(self, code_text):
        with tempfile.NamedTemporaryFile(suffix='.rs', dir='.') as tmpf:
            tmpf.write(code_text.encode('utf8'))
            tmpf.flush()
            cmd = f'rustc -o main {tmpf.name} && ./main'
            await self.run_subproc(cmd)

    async def complete(self, data):
        return []

    async def interrupt(self):
        # subproc interrupt is already handled by BaseRunner
        pass
