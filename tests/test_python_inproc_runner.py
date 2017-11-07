from io import BytesIO, UnsupportedOperation, SEEK_SET
import sys

import pytest

from ai.backend.kernel.python.inproc import ConsoleOutput
from ai.backend.kernel.python.types import ConsoleRecord


def test_console_output():
    output = BytesIO()

    def emit(rec):
        assert isinstance(rec, ConsoleRecord)
        output.write(rec.data)

    stdout = ConsoleOutput(emit, 'stdout')

    # basic properties
    assert stdout.isatty()
    assert stdout.writable()
    assert not stdout.readable()
    assert not stdout.seekable()
    stdout.flush()  # no-op

    # it should not be readable and seekable.
    with pytest.raises(UnsupportedOperation):
        stdout.tell()
    with pytest.raises(UnsupportedOperation):
        stdout.seek(42, SEEK_SET)
    with pytest.raises(UnsupportedOperation):
        stdout.read(1024)
    with pytest.raises(UnsupportedOperation):
        stdout.readline()
    with pytest.raises(UnsupportedOperation):
        stdout.readlines()
    with pytest.raises(UnsupportedOperation):
        stdout.truncate()
    with pytest.raises(OSError):
        stdout.fileno()

    # it should be writable.
    print('wow', file=stdout)
    stdout.write('안녕!')
    stdout.writelines([b'\xaa', b'\xbb'])
    assert output.getvalue() == b'wow\n\xec\x95\x88\xeb\x85\x95!\xaa\xbb'

    # it should follow the documented closing behavior.
    # (of course, closing stdout/stderr would never happen)
    stdout.close()
    stdout.close()  # multiple closing is no-op
    assert stdout.closed
    with pytest.raises(ValueError):
        print('ooo', file=stdout)

    output.close()


def test_console_output_replacing_sys():
    out = BytesIO()
    err = BytesIO()

    def out_emit(rec):
        assert isinstance(rec, ConsoleRecord)
        out.write(rec.data)

    def err_emit(rec):
        assert isinstance(rec, ConsoleRecord)
        err.write(rec.data)

    my_stdout = ConsoleOutput(out_emit, 'stdout')
    my_stderr = ConsoleOutput(err_emit, 'stderr')

    sys.stdout, orig_stdout = my_stdout, sys.stdout
    sys.stderr, orig_stderr = my_stderr, sys.stderr

    print('123', end='')
    print('456', end='', file=sys.stderr)

    sys.stdout = orig_stdout
    sys.stderr = orig_stderr

    print('abc')
    print('def', file=sys.stderr)

    assert out.getvalue() == b'123'
    assert err.getvalue() == b'456'

    out.close()
    err.close()
