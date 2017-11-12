import argparse
import asyncio
import fcntl
import logging
import os
import pty
import shlex
import signal
import struct
import sys
import termios
import traceback

import aiozmq
import simplejson as json
import zmq

log = logging.getLogger()


class StdoutProtocol(asyncio.Protocol):

    def __init__(self, sock_term_out, mother_term):
        self.transport = None
        self.sock_term_out = sock_term_out
        self.term = mother_term

    def connection_made(self, transport):
        self.transport = transport

    def data_received(self, data):
        self.sock_term_out.write([data])

    def connection_lost(self, exc):
        if not self.term.auto_restart:
            self.sock_term_out.write([b'Terminated.\r\n'])
            return
        if not self.term.ev_term.is_set():
            self.sock_term_out.write([b'Restarting...\r\n'])
            os.waitpid(self.term.pid, 0)
            asyncio.ensure_future(self.term.start(), loop=self.term.loop)


class Terminal:
    '''
    A wrapper for a terminal-based app.
    '''

    def __init__(self, shell_cmd, ev_term, sock_out, *,
                 auto_restart=True, loop=None):
        self._sorna_media = []
        self.loop = loop if loop else asyncio.get_event_loop()

        self.ev_term = ev_term
        self.pid = None
        self.fd = None

        self.shell_cmd = shell_cmd
        self.auto_restart = auto_restart

        # For command output
        self.sock_out = sock_out

        # For terminal I/O
        self.sock_term_in  = None
        self.sock_term_out = None

        self.cmdparser = argparse.ArgumentParser()
        self.subparsers = self.cmdparser.add_subparsers()

        # Base commands for generic terminal-based app
        parser_ping = self.subparsers.add_parser('ping')
        parser_ping.set_defaults(func=self.do_ping)

        parser_resize = self.subparsers.add_parser('resize')
        parser_resize.add_argument('rows', type=int)
        parser_resize.add_argument('cols', type=int)
        parser_resize.set_defaults(func=self.do_resize_term)

    def do_ping(self, args):
        self.sock_out.write([b'stdout', b'pong!'])

    def do_resize_term(self, args):
        origsz = struct.pack('HHHH', 0, 0, 0, 0)
        origsz = fcntl.ioctl(self.fd, termios.TIOCGWINSZ, origsz)
        _, _, origx, origy = struct.unpack('HHHH', origsz)
        newsz = struct.pack('HHHH', args.rows, args.cols, origx, origy)
        newsz = fcntl.ioctl(self.fd, termios.TIOCSWINSZ, newsz)
        newr, newc, _, _ = struct.unpack('HHHH', newsz)
        self.sock_out.write([
            b'stdout',
            f'OK; terminal resized to {newr} rows and {newc} cols'.encode(),
        ])

    async def handle_command(self, code_txt):
        try:
            if code_txt.startswith('%'):
                args = self.cmdparser.parse_args(
                    shlex.split(code_txt[1:], comments=True))
                if asyncio.iscoroutine(args.func) or \
                        asyncio.iscoroutinefunction(args.func):
                    await args.func(args)
                else:
                    args.func(args)
            else:
                self.sock_out.write([b'stderr', b'Invalid command.'])
        except:
            exc_type, exc_val, tb = sys.exc_info()
            trace = traceback.format_exception(exc_type, exc_val, tb)
            self.sock_out.write([b'stderr', trace.encode()])
        finally:
            opts = {
                'upload_output_files': False,
            }
            self.sock_out.write([b'finished', json.dumps(opts).encode()])

    async def start(self):
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            args = shlex.split(self.shell_cmd)
            os.execv(args[0], args)
        else:
            if self.sock_term_in is None:
                self.sock_term_in  = await aiozmq.create_zmq_stream(
                    zmq.SUB, bind='tcp://*:2002')
                self.sock_term_in.transport.subscribe(b'')
            if self.sock_term_out is None:
                self.sock_term_out = await aiozmq.create_zmq_stream(
                    zmq.PUB, bind='tcp://*:2003')
            await self.loop.connect_read_pipe(
                lambda: StdoutProtocol(self.sock_term_out, self),
                os.fdopen(self.fd, 'rb'))
            asyncio.ensure_future(self.terminal_in())
            print('opened shell pty: stdin at port 2002, stdout at port 2003')

    async def terminal_in(self):
        while True:
            try:
                data = await self.sock_term_in.read()
            except aiozmq.ZmqStreamClosed:
                break
            try:
                os.write(self.fd, data[0])
            except OSError:
                break

    async def shutdown(self):
        self.sock_term_in.close()
        self.sock_term_out.close()
        os.kill(self.pid, signal.SIGHUP)
        os.kill(self.pid, signal.SIGCONT)
        await asyncio.sleep(0)
        os.waitpid(self.pid, 0)
        self.pid = None
        self.fd = None
        print('terminated term-app.')
