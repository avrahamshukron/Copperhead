from cStringIO import StringIO
from unittest import TestCase
from dummy import Packet, Header


class SimpleRecordTest(TestCase):
    """
    Test simple record with primitive values.
    """

    cases = (
        (dict(barker=0xba5eba11, size=0x1234, inverted_size=0xedcb),
         "\xba\x5e\xba\x11\x12\x34\xed\xcb"),
        (dict(
            barker=Header.barker.min,
            size=Header.size.min,
            inverted_size=Header.inverted_size.min
        ), "\x00\x00\x00\x00\x00\x00\x00\x00"),
        (dict(
            barker=Header.barker.max,
            size=Header.size.max,
            inverted_size=Header.inverted_size.max
        ), "\xff\xff\xff\xff\xff\xff\xff\xff"),
    )

    def test_creation(self):
        for values in (case[0] for case in self.cases):
            h = Header(**values)
            for name, value in values.iteritems():
                self.assertEqual(getattr(h, name), value)

    def test_encoding(self):
        for values, expected in self.cases:
            h = Header(**values)
            buf = Header._encode(h)  # Will call `encode`
            self.assertEqual(buf, expected)

    def test_decoding(self):
        for values, expected in self.cases:
            h, _ = Header._decode(expected)
            for name, value in values.iteritems():
                self.assertEqual(value, getattr(h, name))
