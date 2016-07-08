import struct
from cStringIO import StringIO
from unittest import TestCase

import array

from coders import Coder
from primitives import UnsignedInteger, SignedInteger, Boolean, Enum, Sequence


class CoderTests(TestCase):
    def test_abstraction(self):
        coder = Coder()
        for func, args in (
                (coder.read_from, (None,)),
                (coder.write_to, (None, None)),
                (coder.default_value, ())):
            self.assertRaises(NotImplementedError, func, *args)


class UnsignedIntegerFieldTests(TestCase):

    def test_creation(self):
        """
        Test correct creation of an instance.
        """
        for width in (-1, 0, 3, 5, 6, 7, 9, 10):
            self.assertRaises(ValueError, UnsignedInteger, width=width)

    def test_get_default(self):
        for width in UnsignedInteger.STANDARD_WIDTHS.keys():
            default = 124
            f = UnsignedInteger(width=width, default=default)
            self.assertEqual(f.width, width)
            self.assertEqual(
                f.default_value(), default, msg="Wrong value observed")

    def test_class_bounds(self):
        for width in UnsignedInteger.STANDARD_WIDTHS.keys():
            for value in (-1, 2 ** (8 * width)):
                empty = StringIO()
                f = UnsignedInteger(width=width)
                self.assertRaises(ValueError, f.write_to, value, empty)
                self.assertEqual(f.read_from(StringIO("\x00" * width)), 0)
                self.assertEqual(
                    f.read_from(StringIO("\xff" * width)),
                    2 ** (8 * width) - 1
                )

    def test_user_bounds(self):
        max_value = 123456
        min_value = 100
        unlimited = UnsignedInteger()
        limited = UnsignedInteger(min_value=min_value, max_value=max_value)
        for value in (0, min_value - 1, max_value + 1, 999999):
            buf_in = StringIO()
            self.assertRaises(ValueError, limited.write_to, value, buf_in)
            unlimited.write_to(value, buf_in)
            self.assertRaises(ValueError, limited.read_from, buf_in)

    def test_encoding(self):
        for width in UnsignedInteger.STANDARD_WIDTHS.keys():
            expected = "\x0f" * width
            value = reduce(lambda x, y: (x << 8) + y, [0x0f] * width, 0)
            print hex(value)
            out_buf = StringIO()
            f = UnsignedInteger(width=width)
            f.write_to(value, out_buf)
            self.assertEqual(out_buf.getvalue(), expected)

    def test_decoding(self):
        for width in UnsignedInteger.STANDARD_WIDTHS.keys():
            encoded = StringIO("\x0f" * width)
            value = reduce(lambda x, y: (x << 8) + y, [0x0f] * width, 0)
            f = UnsignedInteger(width=width)
            decoded = f.read_from(encoded)
            self.assertEqual(decoded, value, msg="Incorrect decoded value")
            self.assertEqual(
                encoded.read(), "", msg="Incorrect remaining data")


class SignedIntegerTests(TestCase):

    def test_class_bounds(self):
        for width in SignedInteger.STANDARD_WIDTHS.keys():
            value_bits = 8 * width - 1
            lower_bound = -2 ** value_bits
            upper_bound = 2 ** value_bits - 1
            for value in (lower_bound - 1, upper_bound + 1):
                f = SignedInteger(width=width)
                out_buf = StringIO()
                self.assertRaises(ValueError, f.write_to, value, out_buf)

    def test_encoding_decoding(self):
        for width in SignedInteger.STANDARD_WIDTHS.keys():
            f = SignedInteger(width=width)
            for value, expected_encoding in ((-1, "\xff"), (-127, "\x81"),
                                             (0, "\x00"), (1, "\x01"),
                                             (127, "\x7f"),):
                padding = "\xff" if value < 0 else "\x00"
                expected_encoding = expected_encoding.rjust(width, padding)
                out_buf = StringIO()
                f.write_to(value, out_buf)
                encoded = out_buf.getvalue()
                self.assertEqual(encoded, expected_encoding)

                out_buf.reset()
                decoded_value = f.read_from(out_buf)
                self.assertEqual(
                    out_buf.read(), "", msg="Incorrect remaining buffer")
                self.assertEqual(decoded_value, value)


class BooleanFieldTests(TestCase):

    def test_encoding(self):
        f = Boolean()
        for value, expected in (
                (True, "\x01"), (False, "\x00"),
                (0, "\x00"), (1, "\x01"), (255, "\x01")):
            out_buf = StringIO()
            f.write_to(value, out_buf)
            self.assertEqual(out_buf.getvalue(), expected)

    def test_decoding(self):
        f = Boolean()
        for expected_value, encoded in ((True, "\x01\xff\xff"),
                                        (False, "\x00\xff\xff")):
            buf_in = StringIO(encoded)
            decoded_value = f.read_from(buf_in)
            # Check that the remaining data was not consumed.
            self.assertEqual(
                buf_in.read(), encoded[f.width:],
                msg="Remaining data incorrect")
            buf_in.close()
            # Check that the expected_value is correct
            self.assertEqual(
                decoded_value, expected_value, msg="Incorrect decoded value")


class EnumFieldTests(TestCase):

    VALUES = {
        "One": 1, "Two": 2, "Four": 4, "Eight": 8, "Sixteen": 16,
    }
    numeric_values = VALUES.values()
    struct = struct.Struct("B")

    def test_creation(self):
        e = Enum(members=self.VALUES)
        self.assertEqual(e.width, 1, msg="Incorrect default width")

    def test_encode(self):
        e = Enum(members=self.VALUES)
        for value in self.numeric_values:
            out_buf = StringIO()
            e.write_to(value, out_buf)
            self.assertEqual(out_buf.getvalue(), self.struct.pack(value),
                             msg="Incorrect encoded value")
            out_buf.close()

        not_members = set(range(1, 20)) - set(self.numeric_values)
        for value in not_members:
            out_buf = StringIO()
            self.assertRaises(ValueError, e.write_to, value, out_buf)

    def test_decode(self):
        e = Enum(members=self.VALUES)

        for encoded, value in (
                (self.struct.pack(v), v)
                for v in self.numeric_values):
            in_buf = StringIO(encoded)
            decoded_value = e.read_from(in_buf)
            self.assertEqual(
                decoded_value, value, msg="Incorrect decoded value")

        not_members = set(range(1, 20)) - set(self.numeric_values)
        for encoded in (self.struct.pack(v) for v in not_members):
            in_buf = StringIO(encoded)
            self.assertRaises(ValueError, e.read_from, in_buf)

    def test_enum_api(self):
        e = Enum(self.VALUES)
        for name in self.VALUES.keys():
            self.assertTrue(hasattr(e.members, name))
            self.assertEqual(self.VALUES[name], getattr(e.members, name))


class SequenceTest(TestCase):

    def setUp(self):
        self.uint8 = UnsignedInteger(width=1)
        self.uint32 = UnsignedInteger(width=4, max_value=100)
        self.counted_sequence = Sequence(element_coder=self.uint8,
                                         length_coder=self.uint32)
        self.counless_sequence = Sequence(element_coder=self.uint8,
                                          length_coder=None)

    def test_default_value(self):
        self.assertEqual(self.counted_sequence.default_value(), [])

    def test_encoding_with_length(self):
        for i in xrange(self.uint32.max):
            items = range(i)
            encoded = self.counted_sequence.encode(items)
            a = array.array("B", items)
            expected = self.uint32.encode(i) + a.tostring()
            self.assertEqual(encoded, expected)

    def test_encode_exceeding_length(self):
        self.assertRaises(
            ValueError, self.counted_sequence.encode, [1] * (self.uint32.max + 1))

    def test_decoding_with_length(self):
        for i in xrange(self.uint32.max):
            expected = range(i)
            a = array.array("B", expected)
            encoded = self.uint32.encode(i) + a.tostring()
            items, _ = self.counted_sequence.decode(encoded)
            self.assertEqual(items, expected)

    def test_decoding_without_length(self):
        for i in xrange(100):
            expected = [0xaa] * i
            a = array.array("B", expected)
            encoded = a.tostring()
            items, _ = self.counless_sequence.decode(encoded)
            self.assertEqual(items, expected)

