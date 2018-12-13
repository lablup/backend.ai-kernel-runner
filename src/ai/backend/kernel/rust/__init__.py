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
    'LD_PRELOAD': os.environ.get('LD_PRELOAD', '/home/backend.ai/libbaihook.so'),
}


class Runner(BaseRunner):

    log_prefix = 'rust-kernel'

    def __init__(self):
        super().__init__()
        self.child_env.update(CHILD_ENV)

    async def init_with_loop(self):
        pass

    async def build_heuristic(self) -> int:
        if Path('Cargo.toml').is_file():
            return await self.run_subproc('cargo build')
        elif Path('main.rs').is_file():
            return await self.run_subproc('rustc -o main main.rs')
        else:
            log.error(
                'cannot find the main/build file ("Cargo.toml" or "main.rs").')
            return 127

    async def execute_heuristic(self) -> int:
        out = find_executable('./target/debug', './target/release')
        if out is not None:
            return await self.run_subproc(f'{out}')
        elif Path('./main').is_file():
            return await self.run_subproc('./main')
        else:
            log.error('cannot find executable ("main" or target directories).')
            return 127

    async def query(self, code_text) -> int:
        with tempfile.NamedTemporaryFile(suffix='.rs', dir='.') as tmpf:
            tmpf.write(code_text.encode('utf8'))
            tmpf.flush()
            cmd = f'rustc -o main {tmpf.name} && ./main'
            return await self.run_subproc(cmd)

    async def complete(self, data):
        return []

    async def interrupt(self):
        # subproc interrupt is already handled by BaseRunner
        pass

    async def start_service(self, service_info):
        return None, {}
