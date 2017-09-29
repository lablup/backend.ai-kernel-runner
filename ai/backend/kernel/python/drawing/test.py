from six.moves import builtins
import simplejson as json
import unittest
import math

from . import canvas, Canvas, Vec2D, Turtle, Colors
from .encoding import encode_commands, decode_commands


class CanvasFunctionalTest(unittest.TestCase):

    def test_create(self):
        c = Canvas(100, 100)
        t = c.create_turtle()
        self.assertIsInstance(t, Turtle)

    def test_update(self):
        builtins._sorna_media = []
        canvas._canvas_id_counter = 0
        c = Canvas(100, 120)
        l = c.line(20, 20, 50, 50)
        o = c.circle(10, 10, 30)
        c.update()
        self.assertGreater(len(builtins._sorna_media), 0)
        self.assertEqual(builtins._sorna_media[0][0], u'application/x-sorna-drawing')
        data = builtins._sorna_media[0][1]
        update = decode_commands(data)
        self.assertEqual(0, update[0][0])
        self.assertEqual(u'canvas', update[0][1])
        self.assertEqual(100, update[0][2])
        self.assertEqual(120, update[0][3])
        self.assertEqual(0, update[-2][0])
        self.assertEqual(u'obj', update[-2][1])
        line_id = update[-2][2]
        self.assertEqual(l._id, line_id)
        self.assertEqual(u'line', update[-2][3][0])
        self.assertEqual(0, update[-1][0])
        self.assertEqual(u'obj', update[-1][1])
        circle_id = update[-1][2]
        self.assertEqual(o._id, circle_id)
        self.assertEqual(u'circle', update[-1][3][0])

        builtins._sorna_media = []
        o.set_y(45)
        c.update()
        self.assertGreater(len(builtins._sorna_media), 0)
        self.assertEqual(builtins._sorna_media[0][0], u'application/x-sorna-drawing')
        data = builtins._sorna_media[0][1]
        update = decode_commands(data)
        self.assertEqual(0, update[0][0])
        self.assertEqual(u'update', update[0][1])
        self.assertEqual(circle_id, update[0][2])
        self.assertEqual(u'y', update[0][3])
        self.assertEqual(45, update[0][4])


class ColorFunctionalTest(unittest.TestCase):

    def test_conversion(self):
        self.assertEqual(u'#ff0000ff', Colors.Red.to_hex())
        self.assertEqual(b'\xff\x00\x00\xff', Colors.Red.to_bytes())


class EncodingFunctionalTest(unittest.TestCase):

    def test_size(self):
        c = Canvas(100, 120)
        _ = c.line(20, 20, 50, 50)
        _ = c.circle(10, 10, 30)
        encdata = encode_commands(c._cmd_history)
        jsondata = json.dumps(c._cmd_history)
        self.assertGreater(len(jsondata), len(encdata))

    def test_encoding(self):
        c = Canvas(100, 120)
        _ = c.line(20, 20, 50, 50)
        _ = c.circle(10, 10, 30)
        encdata = encode_commands(c._cmd_history)
        cmds = decode_commands(encdata)
        self.assertListEqual(cmds[0], list(c._cmd_history[0]))


class TurtleFunctionalTest(unittest.TestCase):

    def test_vec2d(self):
        v = Vec2D(1, 0)
        self.assertAlmostEqual(1, abs(v))
        v = Vec2D(1, 1)
        self.assertAlmostEqual(math.sqrt(2), abs(v))

    def test_pos(self):
        c = Canvas(100, 100)
        t = Turtle(c)
        t.setpos(10, 10)
        self.assertTupleEqual((10, 10), t.pos())
        t.setpos(Vec2D(50, 50))
        self.assertTupleEqual((50, 50), t.pos())
