import argparse
import asyncio
import fcntl
import json
import logging
import os
import pty
import shlex
import signal
import struct
import sys
import termios
import traceback

import zmq, zmq.asyncio

from .utils import current_loop

log = logging.getLogger()


class Terminal:
    '''
    A wrapper for a terminal-based app.
    '''

    def __init__(self, shell_cmd, ev_term, sock_out, *,
                 auto_restart=True, loop=None):
        self._sorna_media = []
        self.loop = loop if loop else current_loop()
        self.zctx = sock_out.context

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

    def do_ping(self, args) -> int:
        self.sock_out.write([b'stdout', b'pong!'])
        return 0

    def do_resize_term(self, args) -> int:
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
        return 0

    async def handle_command(self, code_txt) -> int:
        try:
            if code_txt.startswith('%'):
                args = self.cmdparser.parse_args(
                    shlex.split(code_txt[1:], comments=True))
                if asyncio.iscoroutine(args.func) or \
                        asyncio.iscoroutinefunction(args.func):
                    return await args.func(args)
                else:
                    return args.func(args)
            else:
                self.sock_out.write([b'stderr', b'Invalid command.'])
                return 127
        except:
            exc_type, exc_val, tb = sys.exc_info()
            trace = traceback.format_exception(exc_type, exc_val, tb)
            self.sock_out.write([b'stderr', trace.encode()])
            return 1
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
                self.sock_term_in  = self.zctx.socket(zmq.SUB)
                self.sock_term_in.bind('tcp://*:2002')
                self.sock_term_in.transport.subscribe(b'')
            if self.sock_term_out is None:
                self.sock_term_out = self.zctx.socket(zmq.PUB)
                self.sock_term_out.bind('tcp://*:2003')

            term_reader = asyncio.StreamReader()
            term_read_protocol = asyncio.StreamReaderProtocol(self.term_reader)
            await self.loop.connect_read_pipe(
                lambda: term_read_protocol, os.fdopen(self.fd, 'rb'))

            term_writer_transport, term_writer_protocol = \
                await self.loop.connect_write_pipe(asyncio.streams.FlowControlMixin,
                                                   self.fdopen(self.fd, 'wb'))
            term_writer = asyncio.StreamWriter(term_writer_transport,
                                               term_writer_protocol,
                                               None, self.loop)

            self.term_in_task = self.loop.create_task(self.term_in(term_writer))
            self.term_out_task = self.loop.create_task(self.term_out(term_reader))

    async def term_in(self, term_writer):
        while True:
            try:
                data = await self.sock_term_in.recv_multipart()
                if not data:
                    break
                term_writer.write(data[0])
                await term_writer.drain()
            except asyncio.CancelledError:
                break
            except OSError:
                break

    async def term_out(self, term_reader):
        try:
            while not term_reader.at_eof():
                data = await term_reader.read(4096)
                await self.sock_term_out.send_multipart([data])
            # fd is closed
            if not self.auto_restart:
                await self.sock_term_out.send_multipart([b'Terminated.\r\n'])
                return
            if not self.ev_term.is_set():
                await self.sock_term_out.send_multipart([b'Restarting...\r\n'])
                os.waitpid(self.pid, 0)
                self.loop.create_task(self.start(), loop=self.loop)
        except asyncio.CancelledError:
            pass

    async def shutdown(self):
        self.term_in_task.cancel()
        self.term_out_task.cancel()
        await self.term_in_task
        await self.term_out_task
        self.sock_term_in.close()
        self.sock_term_out.close()
        os.kill(self.pid, signal.SIGHUP)
        os.kill(self.pid, signal.SIGCONT)
        await asyncio.sleep(0)
        os.waitpid(self.pid, 0)
        self.pid = None
        self.fd = None
