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
DEFAULT_JFLAGS = ('-XX:+UnlockExperimentalVMOptions '
                  '-XX:+UseCGroupMemoryLimitForHeap -d .')

CHILD_ENV = {
    'TERM': 'xterm',
    'LANG': 'C.UTF-8',
    'SHELL': '/bin/ash',
    'USER': 'work',
    'HOME': '/home/work',
    'PATH': ('/usr/lib/jvm/java-1.8-openjdk/jre/bin:'
             '/usr/lib/jvm/java-1.8-openjdk/bin:/usr/local/sbin:'
             '/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'),
    'LD_PRELOAD': os.environ.get('LD_PRELOAD', '/home/sorna/patch-libs.so'),
}


class Runner(BaseRunner):

    log_prefix = 'java-kernel'

    def __init__(self):
        super().__init__()
        self.child_env = CHILD_ENV

    async def init_with_loop(self):
        pass

    async def build_heuristic(self):
        if Path('Main.java').is_file():
            javafiles = Path('.').glob('**/*.java')
            javafiles = ' '.join(map(lambda p: shlex.quote(str(p)), javafiles))
            cmd = f'{JCC} {DEFAULT_JFLAGS} {javafiles}'
            await self.run_subproc(cmd)
        else:
            javafiles = Path('.').glob('**/*.java')
            javafiles = ' '.join(map(lambda p: shlex.quote(str(p)), javafiles))
            cmd = f'{JCC} {DEFAULT_JFLAGS} {javafiles}'
            await self.run_subproc(cmd)

    async def execute_heuristic(self):
        if Path('./main/Main.class').is_file():
            await self.run_subproc(f'{JCR} main.Main')
        else:
            log.error('cannot find entry class (main.Main).')

    async def query(self, code_text):
        # Parse public class name
        # If public class exists in source file, get the name. The name of the
        # file and the (unique) public class name should match in Java. This
        # approach may not be perfect, so other parsing strategy should be
        # applied in the future.
        m = re.search('public[\s]+class[\s]+([\w]+)[\s]*{', code_text)
        filename = None
        if m and len(m.groups()) > 0:
            filename = f'/home/work/' + m.group(1) + '.java'

        # Save code to a temporary file
        if filename:
            tmpf = open(filename, 'w+b')
        else:
            tmpf = tempfile.NamedTemporaryFile(suffix='.java', dir='.')
        tmpf.write(code_text.encode('utf8'))
        tmpf.flush()

        try:
            cmd = f'{JCC} {filename} && {JCR} {filename.split("/")[-1][:-5]}'
            await self.run_subproc(cmd)
        finally:
            # Close and delete the temporary file.
            tmpf.close()
            if filename:
                os.remove(filename)

    async def complete(self, data):
        return []

    async def interrupt(self):
        # subproc interrupt is already handled by BaseRunner
        pass
