from cStringIO import StringIO
from unittest import TestCase

from containers import RecordBase, Record
from dummy import Header, Packet, Command, GeneralCommands, GetStatus


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
        # Test default values
        h = Header()
        for name, coder in h.members.iteritems():
            self.assertEqual(coder.default_value(), getattr(h, name))
        # Test user-defined values
        for values in (case[0] for case in self.cases):
            h = Header(**values)
            for name, value in values.iteritems():
                self.assertEqual(getattr(h, name), value)

    def test_no_order(self):
        """
        Try to create a Record subclass without an order defined.
        """
        self.assertRaises(ValueError, RecordBase, "NoOrder", (Record,), {})

    def test_invalid_member(self):
        """
        Try to create a Record subclass with a member that is not a Coder.
        """
        attrs = dict(order=("foo",), foo=7)
        self.assertRaises(ValueError, RecordBase, "NoCoder", (Record,), attrs)

    def test_encoding(self):
        for values, expected in self.cases:
            h = Header(**values)
            buf = Header.encode(h)  # Will call `write_to`
            self.assertEqual(buf, expected)

    def test_decoding(self):
        for values, expected in self.cases:
            h, _ = Header.decode(expected)
            for name, value in values.iteritems():
                self.assertEqual(value, getattr(h, name))


class ChoiceTest(TestCase):
    get_status = Command.GeneralCommands.GetStatus(
        is_active=True, uptime=0x1234)

    def test_creation(self):

        self.assertEqual(
            self.get_status.tag, Command.reverse_variants[GeneralCommands])
        self.assertIsInstance(self.get_status.value, GeneralCommands)

        self.assertEqual(
            self.get_status.value.tag,
            GeneralCommands.reverse_variants[GetStatus])
        self.assertIsInstance(self.get_status.value.value, GetStatus)

        self.assertTrue(self.get_status.value.value.is_active)
        self.assertEqual(self.get_status.value.value.uptime, 0x1234)

    def test_encoding(self):
        stream = StringIO()
        # 0x54 for GeneralCommands tag, 0xfa for GetStatus tag,
        # 0x01 for GetStatus.is_active, 0x00001234 for GetStatus.uptime
        expected = "\x54\xfa\x01\x00\x00\x12\x34"
        written = self.get_status.write_to(stream)
        self.assertEqual(written, len(expected))
        self.assertEqual(stream.getvalue(), expected)

    def test_decoding(self):
        # Assuming encoding is tested and working
        encoded = self.get_status.encode()
        decoded, remainder = Command.decode(encoded)
        self.assertEqual(remainder, "")
        self.assertEqual(decoded, self.get_status)
