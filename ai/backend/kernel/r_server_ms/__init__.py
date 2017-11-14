import logging
import os

import aiohttp

from .. import BaseRunner

log = logging.getLogger()


class Runner(BaseRunner):

    '''
    Implements an adaptor to Microsoft R Server API.
    '''

    log_prefix = 'r-server'

    def __init__(self, endpoint=None, credentials=None):
        super().__init__()
        if endpoint is None:
            endpoint = os.environ.get('MRS_ENDPOINT', 'localhost')
        if credentials is None:
            credentials = {
                'username': os.environ.get('MRS_USERNAME', 'anonymous'),
                'password': os.environ.get('MRS_PASSWORD', 'unknown'),
            }
        self.http_sess = aiohttp.ClientSession()
        self.endpoint = endpoint
        self.credentials = credentials

    async def init_with_loop(self):
        login_url = self.endpoint + '/login'
        resp = await self.http_sess.post(login_url, json=self.credentials)
        data = await resp.json()
        self.access_token = data['access_token']
        self.auth_hdrs = {
            'Authorization': 'Bearer {}'.format(self.access_token),
        }
        print('access token:', self.access_token)
        sess_create_url = self.endpoint + '/sessions'
        resp = await self.http_sess.post(
            sess_create_url,
            headers=self.auth_hdrs,
            json={})
        data = await resp.json()
        self.sess_id = data['sessionId']
        print('created session:', self.sess_id)
        self.init_done.set()

    async def shutdown(self):
        sess_url = f'{self.endpoint}/sessions/{self.sess_id}'
        await self.http_sess.delete(sess_url)
        print('deleted session:', self.sess_id)
        await self.http_sess.close()

    async def build_heuristic(self):
        raise NotImplementedError

    async def execute_heuristic(self):
        raise NotImplementedError

    async def query(self, code_text):
        execute_url = f'{self.endpoint}/sessions/{self.sess_id}/execute'
        resp = await self.http_sess.post(
            execute_url,
            headers=self.auth_hdrs,
            json={
                'code': code_text,
            })
        data = await resp.json()
        self.outsock.write(['stdout', data['consoleOutput']])

    async def complete(self, data):
        return []

    async def interrupt(self):
        pass
