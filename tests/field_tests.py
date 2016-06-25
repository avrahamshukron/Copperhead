from unittest import TestCase

from fields import BooleanField, UnsignedIntegerField, SignedIntegerField


class UnsignedIntegerFieldTests(TestCase):

    def test_creation(self):
        """
        Test correct creation of an instance.
        """
        for width in (-1, 0, 3, 5, 6, 7, 9, 10):
            self.failUnlessRaises(ValueError, UnsignedIntegerField, width=width)

        for width in UnsignedIntegerField.STANDARD_WIDTHS.keys():
            initial_value = 124
            f = UnsignedIntegerField(width=width, initial_value=initial_value)
            self.failUnlessEqual(f.width, width)
            self.failUnlessEqual(
                f.value, initial_value, msg="Wrong value observed")

    def test_class_bounds(self):
        for width in UnsignedIntegerField.STANDARD_WIDTHS.keys():
            for value in (-1, 2 ** (8 * width)):
                f = UnsignedIntegerField(width=width, initial_value=value)
                self.failUnlessRaises(ValueError, f.encode)
                f.decode("\x00" * width)
                f.decode("\xff" * width)

    def test_user_bounds(self):
        max_value = 123456
        min_value = 100
        unlimited = UnsignedIntegerField()
        limited = UnsignedIntegerField(min_value=min_value, max_value=max_value)
        for value in (0, min_value - 1, max_value + 1, 999999):
            limited.value = value
            self.failUnlessRaises(ValueError, limited.encode)
            unlimited.value = value
            encoded = unlimited.encode()
            self.failUnlessRaises(ValueError, limited.decode, encoded)

    def test_encoding(self):
        for width in UnsignedIntegerField.STANDARD_WIDTHS.keys():
            expected = "\x0f" * width
            value = reduce(lambda x, y: (x << 8) + y, [0x0f] * width, 0)
            print hex(value)
            f = UnsignedIntegerField(width=width, initial_value=value)
            self.failUnlessEqual(f.encode(), expected)

    def test_decoding(self):
        for width in UnsignedIntegerField.STANDARD_WIDTHS.keys():
            encoded = "\x0f" * width
            value = reduce(lambda x, y: (x << 8) + y, [0x0f] * width, 0)
            f = UnsignedIntegerField(width=width)
            remaining = f.decode(encoded)
            self.failUnlessEqual(f.value, value, msg="Incorrect decoded value")
            self.failIf(remaining, msg="Incorrect remaining data")


class SignedIntegerTests(TestCase):

    def test_class_bounds(self):
        for width in SignedIntegerField.STANDARD_WIDTHS.keys():
            value_bits = 8 * width - 1
            lower_bound = -2 ** value_bits
            upper_bound = 2 ** value_bits - 1
            for value in (lower_bound - 1, upper_bound + 1):
                f = SignedIntegerField(width=width, initial_value=value)
                self.failUnlessRaises(ValueError, f.encode)

    def test_encoding_decoding(self):
        for width in SignedIntegerField.STANDARD_WIDTHS.keys():
            f = SignedIntegerField(width=width)
            for value, encoded in ((-1, "\xff"),):
                f.value = value
                padding = "\xff" if value < 0 else "\x00"
                encoded = encoded.rjust(width, padding)
                self.failUnlessEqual(f.encode(), encoded)

                # Flip sign just to make sure that the next test won't just have
                # the correct value from before.
                f.value *= -1
                remaining = f.decode(encoded)
                self.failIf(remaining, msg="Incorrect remaining buffer")
                self.failUnlessEqual(f.value, value)


class BooleanFieldTests(TestCase):

    def test_encoding(self):
        f = BooleanField()
        for value, expected in (
                (True, "\x01"), (False, "\x00"),
                (0, "\x00"), (1, "\x01"), (255, "\x01")):
            f.value = value
            self.assertEqual(f.encode(), expected)

    def test_decoding(self):
        f = BooleanField()
        for value, encoded in ((True, "\x01\xff\xff"), (False, "\x00\xff\xff")):
            rest = f.decode(encoded)
            # Check that the remaining data was not consumed.
            self.assertEqual(
                rest, encoded[f.width:], msg="Remaining data incorrect")
            # Check that the value is correct
            self.assertEqual(f.value, value, msg="Decoded value incorrect")
