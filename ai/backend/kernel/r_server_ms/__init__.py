import logging

from .. import BaseRunner

log = logging.getLogger()

ENDPOINT = 'https://...'


class Runner(BaseRunner):

    '''
    Implements an adaptor to Microsoft R Server API.
    '''

    log_prefix = 'r-server'

    def __init__(self):
        super().__init__()

    async def init_with_loop(self):
        # TODO: R server API: create session
        pass

    async def shutdown(self):
        # TODO: R server API: close session
        pass

    async def build_heuristic(self):
        raise NotImplementedError

    async def execute_heuristic(self):
        raise NotImplementedError

    async def query(self, code_text):
        # TODO: R server API: execute
        # TODO: send the result
        self.outsock.write(['stdout', '...'])
        self.outsock.write(['stderr', '...'])

    async def complete(self, data):
        return []

    async def interrupt(self):
        pass
