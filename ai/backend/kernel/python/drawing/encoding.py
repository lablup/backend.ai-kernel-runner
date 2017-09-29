import base64
import umsgpack


def encode_commands(cmdlist):
    bindata = umsgpack.packb(cmdlist)
    return base64.b64encode(bindata).decode('ascii')


def decode_commands(data):
    return umsgpack.unpackb(base64.b64decode(data))
