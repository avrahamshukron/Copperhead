from unittest import TestCase

from fields import BooleanField, SignedIntegerField


class SignedIntegerFieldTests(TestCase):

    def test_creation(self):
        for width in (-1, 0):
            self.failUnlessRaises(ValueError, SignedIntegerField, width=width)

        for width in range(1, 10):
            f = SignedIntegerField(width=width)
            self.failUnlessEqual(f.width, width)

    def test_encoding(self):
        pass

    def test_decoding(self):
        pass


class BooleanFieldTests(TestCase):

    def test_encoding(self):
        f = BooleanField()
        for value, expected in (
                (True, "\x01"), (False, "\x00"),
                (1, "\x01"), (0, "\x00"),
                ("asd", "\x01"), ("", "\x00"),):
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
