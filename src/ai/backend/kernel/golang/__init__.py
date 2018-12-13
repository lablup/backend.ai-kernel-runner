import logging
from pathlib import Path
import shlex
import tempfile

from .. import BaseRunner

log = logging.getLogger()

DEFAULT_BFLAGS = ''
CHILD_ENV = {
    'TERM': 'xterm',
    'LANG': 'C.UTF-8',
    'SHELL': '/bin/ash',
    'USER': 'work',
    'HOME': '/home/work',
    'PATH': '/home/work/bin:/go/bin:/usr/local/go/bin:' +
            '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
    'GOPATH': '/home/work',
}


class Runner(BaseRunner):

    log_prefix = 'go-kernel'

    def __init__(self):
        super().__init__()
        self.child_env.update(CHILD_ENV)

    async def init_with_loop(self):
        pass

    async def build_heuristic(self) -> int:
        if Path('main.go').is_file():
            gofiles = Path('.').glob('**/*.go')
            gofiles = ' '.join(map(lambda p: shlex.quote(str(p)), gofiles))
            cmd = f'go build -o main {DEFAULT_BFLAGS} {gofiles}'
            return await self.run_subproc(cmd)
        else:
            log.error('cannot find main file ("main.go").')
            return 127

    async def execute_heuristic(self) -> int:
        if Path('./main').is_file():
            return await self.run_subproc('./main')
        else:
            log.error('cannot find executable ("main").')
            return 127

    async def query(self, code_text) -> int:
        with tempfile.NamedTemporaryFile(suffix='.go', dir='.') as tmpf:
            tmpf.write(code_text.encode('utf8'))
            tmpf.flush()
            cmd = f'go run {tmpf.name}'
            return await self.run_subproc(cmd)

    async def complete(self, data):
        return []

    async def interrupt(self):
        # subproc interrupt is already handled by BaseRunner
        pass

    async def start_service(self, service_info):
        return None, {}
