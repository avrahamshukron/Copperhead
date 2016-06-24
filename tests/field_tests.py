from unittest import TestCase

from fields import BooleanField, UnsignedIntegerField


class UnsignedIntegerFieldTests(TestCase):

    def test_creation(self):
        for width in (-1, 0):
            self.failUnlessRaises(ValueError, UnsignedIntegerField, width=width)

        for width in range(1, 10):
            f = UnsignedIntegerField(width=width)
            self.failUnlessEqual(f.width, width)

    def test_decode_using_int(self):
        if not hasattr(int, "from_bytes"):
            self.skipTest("Old python version. No int.from_bytes method")

        for width in range(1, 4):
            f = UnsignedIntegerField(width=width)
            self.failUnless(
                f._decode_func == f._decode_using_int,
                msg="Wrong decoding function"
            )

    def test_encoding_width(self):
        for width in range(1, 10):
            f = UnsignedIntegerField(width=width)
            self.failUnlessEqual(f.encode(), "\x00" * width)

    def test_decoding(self):
        pass


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
