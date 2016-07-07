from unittest import TestCase

from containers import RecordBase, Record
from dummy import Header


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


class NestedRecordTest(TestCase):

    def test_encoding(self):
        pass

    def test_decoding(self):
        pass


class ChoiceTest(TestCase):
    pass
