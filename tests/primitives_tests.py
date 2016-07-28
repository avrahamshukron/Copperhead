import array
from cStringIO import StringIO
from unittest import TestCase

from protopy.coders import Coder
from protopy.primitives import UnsignedInteger, SignedInteger, Boolean, \
    Sequence, String


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


class SequenceTest(TestCase):
    def setUp(self):
        self.uint8 = UnsignedInteger(width=1)
        self.with_length = Sequence(element_coder=self.uint8,
                                    max_length=100, include_length=True)
        self.without_length = Sequence(element_coder=self.uint8,
                                       max_length=100, include_length=False)

    def test_default_value(self):
        self.assertEqual(self.with_length.default_value(), [])

    def test_encoding_with_length(self):
        for i in xrange(self.with_length.min, self.with_length.max):
            items = [0x34] * i
            encoded = self.with_length.encode(items)
            a = array.array("B", items)
            expected = self.with_length.length_coder.encode(i) + a.tostring()
            self.assertEqual(encoded, expected)

    def test_encoding_without_length(self):
        for i in xrange(100):
            items = range(i)
            encoded = self.without_length.encode(items)
            a = array.array("B", items)
            self.assertEqual(encoded, a.tostring())

    def test_boundaries(self):
        bounded = Sequence(
            element_coder=self.uint8,
            min_length=10,
            max_length=1024)
        cases = (bounded.max + 1, bounded.min - 1)
        for length in cases:
            print length
            to_encode = [1] * length
            self.assertRaises(ValueError, bounded.encode, to_encode)

        to_decode = "\x01" * (bounded.max + 1)
        decoded, _ = bounded.decode(to_decode)
        self.assertEqual(len(decoded), bounded.max)

        to_decode = "\x01" * (bounded.min - 1)
        self.assertRaises(ValueError, bounded.decode, to_decode)

    def test_decoding_with_length(self):
        for i in (self.with_length.min, self.with_length.max):
            expected = [0x12] * i
            encoded = self.with_length.encode(expected)
            items, _ = self.with_length.decode(encoded)
            self.assertEqual(items, expected)

    def test_decoding_without_length(self):
        for i in (self.without_length.min, self.without_length.max):
            expected = [0xaa] * i
            a = array.array("B", expected)
            encoded = a.tostring()
            items, _ = self.without_length.decode(encoded)
            self.assertEqual(items, expected)


class StringTest(TestCase):
    unlimited = String()
    limited = String(max_length=100)

    def test_default_value(self):
        self.assertEqual(self.limited.default_value(), "")

    def test_encoding(self):
        s = "Hello World"
        expected = s + String.NULL
        self.compare_encoding(expected, s, self.limited)

        # Non-ascii string
        s = "Hello \xff World"
        self.assertRaises(ValueError, self.limited.encode, s)

        # Out-of-bounds
        s = "a" * (self.limited.max_length + 1)
        self.assertRaises(ValueError, self.limited.encode, s)

    def compare_encoding(self, expected, original, coder):
        self.assertEqual(expected, coder.encode(original))
        stream = StringIO()
        written = coder.write_to(original, stream)
        self.assertEqual(written, len(expected))
        self.assertEqual(stream.getvalue(), expected)

    def test_decoding_with_length(self):
        s = "Hello World"
        encoded = s + String.NULL
        self.compare_decoding(encoded, s, self.limited)

        # Non-ascii string
        s = "Hello \xff World" + String.NULL
        self.assertRaises(ValueError, self.limited.decode, s)

        # Out-of-bounds
        s = "a" * (self.limited.max_length + 1) + String.NULL
        self.assertRaises(ValueError, self.limited.decode, s)

    def compare_decoding(self, expected, original, coder):
        decoded, _ = coder.decode(expected)
        self.assertEqual(decoded, original)
        stream = StringIO(expected)
        self.assertEqual(coder.read_from(stream), original)
