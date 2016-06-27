from unittest import TestCase

import struct

from cStringIO import StringIO

from fields import BooleanField, UnsignedIntegerField, SignedIntegerField, \
    EnumField, Enum


class UnsignedIntegerFieldTests(TestCase):

    def test_creation(self):
        """
        Test correct creation of an instance.
        """
        for width in (-1, 0, 3, 5, 6, 7, 9, 10):
            self.failUnlessRaises(ValueError, UnsignedIntegerField, width=width)

    def test_get_default(self):
        for width in UnsignedIntegerField.STANDARD_WIDTHS.keys():
            default = 124
            f = UnsignedIntegerField(width=width, default=default)
            self.failUnlessEqual(f.width, width)
            self.failUnlessEqual(
                f.get_default(), default, msg="Wrong value observed")

    def test_class_bounds(self):
        for width in UnsignedIntegerField.STANDARD_WIDTHS.keys():
            for value in (-1, 2 ** (8 * width)):
                empty = StringIO()
                f = UnsignedIntegerField(width=width)
                self.failUnlessRaises(ValueError, f.encode, value, empty)
                self.failUnlessEqual(f.decode(StringIO("\x00" * width)), 0)
                self.failUnlessEqual(
                    f.decode(StringIO("\xff" * width)),
                    2 ** (8 * width) - 1
                )

    def test_user_bounds(self):
        max_value = 123456
        min_value = 100
        unlimited = UnsignedIntegerField()
        limited = UnsignedIntegerField(min_value=min_value, max_value=max_value)
        for value in (0, min_value - 1, max_value + 1, 999999):
            buf_in = StringIO()
            self.failUnlessRaises(ValueError, limited.encode, value, buf_in)
            unlimited.encode(value, buf_in)
            self.failUnlessRaises(ValueError, limited.decode, buf_in)

    def test_encoding(self):
        for width in UnsignedIntegerField.STANDARD_WIDTHS.keys():
            expected = "\x0f" * width
            value = reduce(lambda x, y: (x << 8) + y, [0x0f] * width, 0)
            print hex(value)
            out_buf = StringIO()
            f = UnsignedIntegerField(width=width)
            f.encode(value, out_buf)
            self.failUnlessEqual(out_buf.getvalue(), expected)

    def test_decoding(self):
        for width in UnsignedIntegerField.STANDARD_WIDTHS.keys():
            encoded = StringIO("\x0f" * width)
            value = reduce(lambda x, y: (x << 8) + y, [0x0f] * width, 0)
            f = UnsignedIntegerField(width=width)
            decoded = f.decode(encoded)
            self.failUnlessEqual(decoded, value, msg="Incorrect decoded value")
            self.failUnlessEqual(
                encoded.read(), "", msg="Incorrect remaining data")


class SignedIntegerTests(TestCase):

    def test_class_bounds(self):
        for width in SignedIntegerField.STANDARD_WIDTHS.keys():
            value_bits = 8 * width - 1
            lower_bound = -2 ** value_bits
            upper_bound = 2 ** value_bits - 1
            for value in (lower_bound - 1, upper_bound + 1):
                f = SignedIntegerField(width=width)
                out_buf = StringIO()
                self.failUnlessRaises(ValueError, f.encode, value, out_buf)

    def test_encoding_decoding(self):
        for width in SignedIntegerField.STANDARD_WIDTHS.keys():
            f = SignedIntegerField(width=width)
            for value, expected_encoding in ((-1, "\xff"), (-127, "\x81"),
                                             (0, "\x00"), (1, "\x01"),
                                             (127, "\x7f"),):
                padding = "\xff" if value < 0 else "\x00"
                expected_encoding = expected_encoding.rjust(width, padding)
                out_buf = StringIO()
                f.encode(value, out_buf)
                encoded = out_buf.getvalue()
                self.failUnlessEqual(encoded, expected_encoding)

                out_buf.reset()
                decoded_value = f.decode(out_buf)
                self.failUnlessEqual(
                    out_buf.read(), "", msg="Incorrect remaining buffer")
                self.failUnlessEqual(decoded_value, value)


class BooleanFieldTests(TestCase):

    def test_encoding(self):
        f = BooleanField()
        for value, expected in (
                (True, "\x01"), (False, "\x00"),
                (0, "\x00"), (1, "\x01"), (255, "\x01")):
            out_buf = StringIO()
            f.encode(value, out_buf)
            self.assertEqual(out_buf.getvalue(), expected)

    def test_decoding(self):
        f = BooleanField()
        for expected_value, encoded in ((True, "\x01\xff\xff"),
                                        (False, "\x00\xff\xff")):
            buf_in = StringIO(encoded)
            decoded_value = f.decode(buf_in)
            # Check that the remaining data was not consumed.
            self.failUnlessEqual(
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
        e = EnumField(values=self.VALUES)
        self.failUnlessEqual(e.width, 1, msg="Incorrect default width")

    def test_encode(self):
        e = EnumField(values=self.VALUES)
        for value in self.numeric_values:
            out_buf = StringIO()
            e.encode(value, out_buf)
            self.failUnlessEqual(out_buf.getvalue(), self.struct.pack(value),
                                 msg="Incorrect encoded value")
            out_buf.close()

        not_members = set(range(1, 20)) - set(self.numeric_values)
        for value in not_members:
            out_buf = StringIO()
            self.failUnlessRaises(ValueError, e.encode, value, out_buf)

    def test_decode(self):
        e = EnumField(values=self.VALUES)

        for encoded, value in (
                (self.struct.pack(v), v)
                for v in self.numeric_values):
            in_buf = StringIO(encoded)
            decoded_value = e.decode(in_buf)
            self.failUnlessEqual(
                decoded_value, value, msg="Incorrect decoded value")

        not_members = set(range(1, 20)) - set(self.numeric_values)
        for encoded in (self.struct.pack(v) for v in not_members):
            in_buf = StringIO(encoded)
            self.failUnlessRaises(ValueError, e.decode, in_buf)

    def test_enum_api(self):
        e = Enum(self.VALUES)
        self.failUnless(hasattr(e, "One"))
        self.failUnless(hasattr(e, "Two"))
        self.failUnless(hasattr(e, "Four"))
        self.failUnless(hasattr(e, "Eight"))
        self.failUnless(hasattr(e, "Sixteen"))
