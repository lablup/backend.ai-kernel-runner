import builtins as builtin_mod
import code
from functools import partial
from io import IOBase, UnsupportedOperation
import json
import logging
import sys
import traceback
import threading
import types

from IPython.core.completer import Completer

import getpass

from .display import display
from .types import (
    ConsoleRecord, MediaRecord, HTMLRecord,
)


log = logging.getLogger()


class ConsoleOutput(IOBase):

    def __init__(self, emit, stream_type):
        self._emit = emit
        self._stream_type = stream_type

    def readable(self):
        return False

    def writable(self):
        return True

    def seekable(self):
        return False

    def fileno(self):
        raise OSError(f'{self._stream_type} has no file descriptor '
                      'because it is a virtual console.')

    def read(self, *args, **kwargs):
        raise UnsupportedOperation()

    def write(self, s):
        if self.closed:
            raise ValueError('Cannot write to the closed console.')
        if isinstance(s, str):
            s = s.encode('utf8')
        self._emit(ConsoleRecord(self._stream_type, s))

    def flush(self):
        pass

    def isatty(self):
        return True


class PythonInprocRunner(threading.Thread):
    '''
    A thin wrapper for REPL.

    It creates a dummy module that user codes run and keeps the references to
    user-created objects (e.g., variables and functions).
    '''

    def __init__(self, input_queue, output_queue, user_input_queue, sentinel):
        super().__init__(name='InprocRunner', daemon=True)

        # for interoperability with the main asyncio loop
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.user_input_queue = user_input_queue
        self.sentinel = sentinel

        self.stdout = ConsoleOutput(self.emit, 'stdout')
        self.stderr = ConsoleOutput(self.emit, 'stderr')

        # Initialize user module and namespaces.
        user_module = types.ModuleType(
            '__main__',
            doc='Automatically created module for the interactive shell.')
        user_module.__dict__.setdefault('__builtin__', builtin_mod)
        user_module.__dict__.setdefault('__builtins__', builtin_mod)
        self.user_module = user_module
        self.user_ns = user_module.__dict__

        self.completer = Completer(namespace=self.user_ns, global_namespace={})
        self.completer.limit_to__all__ = True

    def run(self):
        # User code is executed in a separate thread.
        while True:
            code_text = self.input_queue.get()
            self.input_queue.task_done()

            # Set Backend.AI Media handler
            self.user_module.__builtins__._sorna_emit = self.emit
            self.user_module.__builtins__.display = display

            # Override interactive input functions
            self.user_module.__builtins__.input = self.handle_input
            getpass.getpass = partial(self.handle_input, password=True)

            try:
                code_obj = code.compile_command(code_text, symbol='exec')
            except (OverflowError, IndentationError, SyntaxError,
                    ValueError, TypeError, MemoryError):
                exc_type, exc_val, tb = sys.exc_info()
                user_tb = type(self).strip_traceback(tb)
                err_str = ''.join(traceback.format_exception(exc_type, exc_val,
                                                             user_tb))
                hdr_str = 'Traceback (most recent call last):\n' \
                        if not err_str.startswith('Traceback ') else ''
                self.stderr.write(hdr_str + err_str)
                self.output_queue.put(self.sentinel)
            else:
                sys.stdout, orig_stdout = self.stdout, sys.stdout
                sys.stderr, orig_stderr = self.stderr, sys.stderr
                try:
                    exec(code_obj, self.user_ns)
                except KeyboardInterrupt:
                    print('Interrupted!', file=self.stderr)
                except Exception:
                    # strip the first frame
                    exc_type, exc_val, tb = sys.exc_info()
                    user_tb = type(self).strip_traceback(tb)
                    traceback.print_exception(exc_type, exc_val, user_tb,
                                              file=sys.stderr)
                finally:
                    sys.stdout = orig_stdout
                    sys.stderr = orig_stderr
                    self.output_queue.put(self.sentinel)

    def handle_input(self, prompt=None, password=False):
        if prompt is None:
            prompt = 'Password: ' if password else ''
        # Use synchronous version of ZeroMQ sockets
        if prompt:
            self.output_queue.put([
                b'stdout',
                prompt.encode('utf8'),
            ])
        self.output_queue.put([
            b'waiting-input',
            json.dumps({'is_password': password}).encode('utf8'),
        ])
        data = self.user_input_queue.get()
        return data

    def complete(self, data):
        # This method is executed in the main thread.
        state = 0
        matches = []
        while True:
            ret = self.completer.complete(data['line'], state)
            if ret is None:
                break
            matches.append(ret)
            state += 1
        return matches

    def emit(self, record):
        if isinstance(record, ConsoleRecord):
            assert record.target in ('stdout', 'stderr')
            self.output_queue.put([
                record.target.encode('ascii'),
                record.data,
            ])
        elif isinstance(record, MediaRecord):
            self.output_queue.put([
                b'media',
                json.dumps({
                    'type': record.type,
                    'data': record.data,
                }).encode('utf8'),
            ])
        elif isinstance(record, HTMLRecord):
            self.output_queue.put([
                b'html',
                record.html.encode('utf8'),
            ])
        elif isinstance(record, tuple):  # raw output
            assert isinstance(record[0], bytes), 'emit: Raw record must be bytes.'
            assert isinstance(record[1], bytes), 'emit: Raw record must be bytes.'
            self.output_queue.put(record)
        else:
            raise TypeError('Unsupported record type.')

    @staticmethod
    def strip_traceback(tb):
        while tb is not None:
            frame_summary = traceback.extract_tb(tb, limit=1)[0]
            if frame_summary[0] == '<input>':
                break
            tb = tb.tb_next
        return tb
