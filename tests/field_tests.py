from unittest import TestCase

from fields import BooleanField, UnsignedIntegerField


class UnsignedIntegerFieldTests(TestCase):

    def test_creation(self):
        """
        Test correct creation of an instance.
        """
        for width in (-1, 0):
            self.failUnlessRaises(ValueError, UnsignedIntegerField, width=width)

        for width in range(1, 10):
            initial_value = 124
            f = UnsignedIntegerField(width=width, initial_value=initial_value)
            self.failUnlessEqual(f.width, width)
            self.failUnlessEqual(
                f.value, initial_value, msg="Wrong value observed")

    def test_class_bounds(self):
        """
        Test upper and lower bounds of this class.

        Verify that encoding fails when trying to encode a value outside the
        class's bounds.
        """
        for width in range(1, 10):
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

    def test_encode_func_selection(self):
        for width in (1, 2, 4, 8):
            f = UnsignedIntegerField(width=width)
            self.failUnless(
                f._encode_func == f._encode_using_struct,
                msg="Wrong encoding method. Expected _encode_using_struct")

        for width in (3, 5, 6, 7, 9, 10):
            f = UnsignedIntegerField(width=width)
            self.failUnless(
                f._encode_func == f._encode_using_binascii,
                msg="Wrong encoding method. Expected _encode_using_binascii")

    def test_decode_func_selection(self):
        if hasattr(int, "from_bytes"):
            # from_int should always be used for decoding
            for width in range(1, 10):
                f = UnsignedIntegerField(width=width)
                self.failUnless(
                    f._decode_func == f._decode_using_int,
                    msg="Wrong decoding function"
                )
        else:
            self.python2_decode_func_selection_test()

    def python2_decode_func_selection_test(self):
        for width in (1, 2, 4, 8):
            f = UnsignedIntegerField(width=width)
            self.failUnless(
                f._decode_func == f._decode_using_struct,
                msg="Wrong decoding method. Expected _decode_using_struct")

        for width in (3, 5, 6, 7, 9, 10):
            f = UnsignedIntegerField(width=width)
            self.failUnless(
                f._decode_func == f._decode_manually,
                msg="Wrong decoding method. Expected _decode_manually")

    def test_encoding(self):
        for width in range(1, 10):
            expected = "\x0f" * width
            value = reduce(lambda x, y: (x << 8) + y, [0x0f] * width, 0)
            print hex(value)
            f = UnsignedIntegerField(width=width, initial_value=value)
            self.failUnlessEqual(f.encode(), expected)

    def test_decoding(self):
        for width in range(1, 10):
            encoded = "\x0f" * width
            value = reduce(lambda x, y: (x << 8) + y, [0x0f] * width, 0)
            f = UnsignedIntegerField(width=width)
            remaining = f.decode(encoded)
            self.failUnlessEqual(f.value, value, msg="Incorrect decoded value")
            self.failIf(remaining, msg="Incorrect remaining data")


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
