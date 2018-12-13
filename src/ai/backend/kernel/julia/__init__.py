import logging
import os
from pathlib import Path
import tempfile

from .. import BaseRunner

log = logging.getLogger()

CHILD_ENV = {
    'TERM': 'xterm',
    'LANG': 'C.UTF-8',
    'SHELL': '/bin/ash',
    'USER': 'work',
    'HOME': '/home/work',
    'PATH': ('/usr/local/julia:/usr/local/julia/bin:/usr/local/sbin:'
             '/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'),
    'LD_PRELOAD': os.environ.get('LD_PRELOAD', '/home/backend.ai/libbaihook.so'),
}


class Runner(BaseRunner):

    log_prefix = 'julia-kernel'

    def __init__(self):
        super().__init__()
        self.child_env.update(CHILD_ENV)

    async def init_with_loop(self):
        pass

    async def build_heuristic(self) -> int:
        log.info('no build process for julia language')
        return 0

    async def execute_heuristic(self) -> int:
        if Path('main.jl').is_file():
            cmd = 'julia main.jl'
            return await self.run_subproc(cmd)
        else:
            log.error('cannot find executable ("main.jl").')
            return 127

    async def query(self, code_text) -> int:
        with tempfile.NamedTemporaryFile(suffix='.jl', dir='.') as tmpf:
            tmpf.write(code_text.encode('utf8'))
            tmpf.flush()
            cmd = f'julia {tmpf.name}'
            return await self.run_subproc(cmd)

    async def complete(self, data):
        return []

    async def interrupt(self):
        # subproc interrupt is already handled by BaseRunner
        pass

    async def start_service(self, service_info):
        return None, {}
