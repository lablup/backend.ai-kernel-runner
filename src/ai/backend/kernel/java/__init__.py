import asyncio
import logging
import os
import re
from pathlib import Path
import shlex
import tempfile

from .. import BaseRunner

log = logging.getLogger()

JCC = 'javac'
JCR = 'java'

# Let Java respect container resource limits
DEFAULT_JFLAGS = ('-J-XX:+UnlockExperimentalVMOptions '
                  '-J-XX:+UseCGroupMemoryLimitForHeap -d .')

CHILD_ENV = {
    'TERM': 'xterm',
    'LANG': 'C.UTF-8',
    'SHELL': '/bin/ash',
    'USER': 'work',
    'HOME': '/home/work',
    'PATH': ('/usr/lib/jvm/java-1.8-openjdk/jre/bin:'
             '/usr/lib/jvm/java-1.8-openjdk/bin:/usr/local/sbin:'
             '/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'),
    'LD_PRELOAD': os.environ.get('LD_PRELOAD', '/home/backend.ai/libbaihook.so'),
}


class Runner(BaseRunner):

    log_prefix = 'java-kernel'

    def __init__(self):
        super().__init__()
        self.child_env = CHILD_ENV

    def _code_for_user_input_server(self, code: str) -> str:
        # TODO: More elegant way of not touching user code? This method does not work
        #       for batch exec (no way of knowing the main file).
        #       Way of monkey patching System.in?
        modules = 'import java.io.*;'
        static_initializer = (r'\1static{BackendInputStream stream = '
                              r'new BackendInputStream();System.setIn(stream);}')
        patch = Path(os.path.dirname(__file__)) / 'LablupPatches.java'
        altered = re.sub(r'(public[\s]+class[\s]+[\w]+[\s]*{)', static_initializer,
                         code)
        altered = modules + altered
        altered = altered + '\n\n' + patch.read_text()
        return altered

    async def init_with_loop(self):
        self.user_input_queue = asyncio.Queue()

    async def build_heuristic(self) -> int:
        if Path('Main.java').is_file():
            javafiles = Path('.').glob('**/*.java')
            javafiles = ' '.join(map(lambda p: shlex.quote(str(p)), javafiles))
            cmd = f'{JCC} {DEFAULT_JFLAGS} {javafiles}'
            return await self.run_subproc(cmd)
        else:
            javafiles = Path('.').glob('**/*.java')
            javafiles = ' '.join(map(lambda p: shlex.quote(str(p)), javafiles))
            cmd = f'{JCC} {DEFAULT_JFLAGS} {javafiles}'
            return await self.run_subproc(cmd)

    async def execute_heuristic(self) -> int:
        if Path('./main/Main.class').is_file():
            return await self.run_subproc(f'{JCR} main.Main')
        elif Path('./Main.class').is_file():
            return await self.run_subproc(f'{JCR} Main')
        else:
            log.error('cannot find entry class (main.Main).')
            return 127

    async def query(self, code_text) -> int:
        # Try to get the name of the first public class using a simple regular
        # expression and use it as the name of the main source/class file.
        # (In Java, the main function must reside in a public class as a public
        # static void method where the filename must be same to the class name)
        #
        # NOTE: This approach won't perfectly handle all edge cases!
        with tempfile.TemporaryDirectory() as tmpdir:
            m = re.search(r'public[\s]+class[\s]+([\w]+)[\s]*{', code_text)
            if m:
                mainpath = Path(tmpdir) / (m.group(1) + '.java')
            else:
                # TODO: wrap the code using a class skeleton??
                mainpath = Path(tmpdir) / 'main.java'
            code = self._code_for_user_input_server(code_text)
            with open(mainpath, 'w', encoding='utf-8') as tmpf:
                tmpf.write(code)
            cmd = f'{JCC} {mainpath} && ' \
                  f'{JCR} -classpath {tmpdir} {mainpath.stem}'
            return await self.run_subproc(cmd)

    async def complete(self, data):
        return []

    async def interrupt(self):
        # subproc interrupt is already handled by BaseRunner
        pass

    async def start_service(self, service_info):
        return None, {}
